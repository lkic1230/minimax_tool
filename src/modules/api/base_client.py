"""MiniMax API 基础客户端。"""
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
from ..core.constants import (
    CHAT_MODEL_DEFAULT,
    SPEECH_MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    MUSIC_MODELS,
)


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
            "语音模型": SPEECH_MODELS,
            "图像模型": IMAGE_MODELS,
            "视频模型": VIDEO_MODELS,
            "音乐模型": MUSIC_MODELS,
        }

    def validate_api_key(self) -> Dict[str, Any]:
        """校验 API Key 可用性（文本对话端点）。"""
        probe_payload = {
            "model": CHAT_MODEL_DEFAULT,
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
