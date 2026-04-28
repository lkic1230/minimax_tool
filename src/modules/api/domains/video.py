"""视频领域 API。"""
import base64
import os
from pathlib import Path
from typing import Any, Dict, Union

from ...core.constants import (
    VIDEO_MODELS,
    VIDEO_MODEL_DEFAULT,
    VIDEO_DURATIONS_INT,
    VIDEO_DURATION_DEFAULT,
    VIDEO_RESOLUTIONS,
    VIDEO_RESOLUTION_DEFAULT,
)


class VideoDomainMixin:
    """视频生成相关方法。"""

    @staticmethod
    def _normalize_first_frame_image(image: Union[str, Path]) -> str:
        """
        统一 first_frame_image 入参格式：
        - 本地文件路径：读取后转 data URL
        - 已是 URL/data URL/base64：按规则规范化
        """
        image_str = str(image).strip()
        if os.path.isfile(image_str):
            with open(image_str, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
            return f"data:image/jpeg;base64,{img_base64}"

        if image_str.startswith(("http://", "https://", "data:")):
            return image_str

        # 调用方可能直接传了裸 base64，这里补成 data URL
        return f"data:image/jpeg;base64,{image_str}"

    def generate_video(
        self,
        prompt: str,
        model: str = VIDEO_MODEL_DEFAULT,
        duration: int = VIDEO_DURATION_DEFAULT,
        resolution: str = VIDEO_RESOLUTION_DEFAULT,
        prompt_optimizer: bool = True,
        callback_url: str = None,
        save_path: str = None,
    ) -> Dict[str, Any]:
        if model not in VIDEO_MODELS:
            raise ValueError(f"不支持的视频模型: {model}，可选: {', '.join(VIDEO_MODELS)}")
        if duration not in VIDEO_DURATIONS_INT:
            raise ValueError(f"不支持的时长: {duration}，可选: {VIDEO_DURATIONS_INT}")
        if resolution not in VIDEO_RESOLUTIONS:
            raise ValueError(f"不支持的分辨率: {resolution}，可选: {', '.join(VIDEO_RESOLUTIONS)}")

        data = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "prompt_optimizer": prompt_optimizer,
        }
        if callback_url:
            data["callback_url"] = callback_url

        result = self._post("/v1/video_generation", data)
        result["save_path"] = save_path
        return result

    def generate_video_from_image(
        self,
        image: Union[str, Path],
        prompt: str = "",
        model: str = VIDEO_MODEL_DEFAULT,
        duration: int = VIDEO_DURATION_DEFAULT,
        resolution: str = VIDEO_RESOLUTION_DEFAULT,
        prompt_optimizer: bool = True,
        save_path: str = None,
    ) -> Dict[str, Any]:
        if model not in VIDEO_MODELS:
            raise ValueError(f"不支持的视频模型: {model}，可选: {', '.join(VIDEO_MODELS)}")
        if duration not in VIDEO_DURATIONS_INT:
            raise ValueError(f"不支持的时长: {duration}，可选: {VIDEO_DURATIONS_INT}")
        if resolution not in VIDEO_RESOLUTIONS:
            raise ValueError(f"不支持的分辨率: {resolution}，可选: {', '.join(VIDEO_RESOLUTIONS)}")

        data = {
            "model": model,
            "first_frame_image": self._normalize_first_frame_image(image),
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "prompt_optimizer": prompt_optimizer,
        }

        result = self._post("/v1/video_generation", data)
        result["save_path"] = save_path
        return result

    def query_video_task(self, task_id: str) -> Dict[str, Any]:
        return self._get("/v1/video_generation/task_query", {"task_id": task_id})

    def download_video(self, task_id: str = None, save_path: str = None) -> Dict[str, Any]:
        result = self._get("/v1/video_generation/download", {"task_id": task_id})

        if save_path and result.get("data", {}).get("video_url"):
            video_url = result["data"]["video_url"]
            video_data = self._download_url(video_url)

            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(video_data)

            result["saved_path"] = str(save_path)
        return result
