"""MiniMax API 基础客户端。"""
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


class BaseMiniMaxClient:
    """MiniMax API 基础能力：会话、HTTP、通用辅助方法。"""

    BASE_URL = "https://api.minimaxi.com"

    def __init__(self, api_key: str, output_dir: str = None):
        self.api_key = api_key
        self.output_dir = Path(output_dir) if output_dir else Path.home() / ".minimax_tool" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "MiniMax-Tool/1.0.0",
            }
        )

    def _post(self, endpoint: str, data: dict, timeout: int = 120) -> dict:
        """发送 POST 请求，确保 UTF-8 编码。"""
        url = f"{self.BASE_URL}{endpoint}"
        json_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        response = self.session.post(
            url,
            data=json_body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _get(self, endpoint: str, params: dict = None, timeout: int = 30) -> dict:
        """发送 GET 请求。"""
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _download_url(self, url: str) -> bytes:
        """下载 URL 内容。"""
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.content

    def get_available_models(self) -> Dict[str, List[str]]:
        """获取所有可用模型。"""
        return {
            "语音模型": [
                "speech-2.8-hd - 新一代HD语音，情绪渲染自然听感",
                "speech-2.8-turbo - 新一代Turbo语音，极致生成速度",
                "speech-2.6-hd - 极致音质与韵律表现",
                "speech-2.6-turbo - 超低时延，响应灵敏",
                "speech-02-hd - 出色韵律和稳定性",
                "speech-02-turbo - 小语种能力增强",
            ],
            "图像模型": [
                "image-01 - 细腻画面表现，支持文生图/图生图",
                "image-01-live - 手绘、卡通等画风增强",
            ],
            "视频模型-文生视频": [
                "MiniMax-Hailuo-2.3 - 全新模型，肢体动作/表情突破",
                "MiniMax-Hailuo-02 - 1080p原生，SOTA指令遵循",
                "T2V-01-Director - 导演级视频生成",
                "T2V-01 - 标准视频生成",
            ],
            "视频模型-图生视频": [
                "MiniMax-Hailuo-2.3-Fast - 更快更优惠",
                "MiniMax-Hailuo-2.3 - 高质量图生视频",
                "MiniMax-Hailuo-02 - 顶级图生视频",
                "I2V-01-live - 实时图生视频",
                "I2V-01-Director - 导演级图生视频",
            ],
            "音乐模型": [
                "music-2.6 - 以声传情，翻唱入心，器乐入魂",
                "music-cover - 基于参考音频生成翻唱版本",
            ],
        }

    def validate_api_key(self) -> Dict[str, Any]:
        """校验 API Key 可用性（文本对话端点）。"""
        probe_payload = {
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": "ping"}],
            "max_completion_tokens": 8,
            "stream": False,
        }
        url = f"{self.BASE_URL}/v1/chat/completions"
        try:
            response = self.session.post(
                url,
                data=json.dumps(probe_payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=10,
            )

            if response.status_code in (401, 403):
                return {"ok": False, "message": "API Key 无效或无权限（401/403）"}
            if response.status_code == 404:
                return {"ok": False, "message": "对话端点不存在（404），请检查接口路径配置"}
            if response.status_code >= 500:
                return {"ok": False, "message": f"服务暂不可用（HTTP {response.status_code}）"}

            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError:
                    return {"ok": False, "message": "响应不是合法 JSON，无法确认鉴权结果"}
                base_resp = body.get("base_resp", {})
                status_code = base_resp.get("status_code", 0)
                status_msg = base_resp.get("status_msg", "success")

                if status_code == 0:
                    return {"ok": True, "message": "API Key 鉴权通过"}
                if status_code == 1004:
                    return {"ok": False, "message": f"API Key 鉴权失败（{status_code}: {status_msg}）"}
                return {"ok": True, "message": f"鉴权通过，但请求返回业务状态（{status_code}: {status_msg}）"}

            if response.status_code in (400, 422):
                return {"ok": True, "message": f"鉴权通过，参数校验失败（HTTP {response.status_code}）"}
            return {"ok": False, "message": f"校验失败（HTTP {response.status_code}）"}
        except requests.RequestException as e:
            return {"ok": False, "message": f"网络错误: {e}"}

