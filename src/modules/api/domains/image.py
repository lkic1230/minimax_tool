"""图像领域 API。"""
import time
from pathlib import Path
from typing import Any, Dict


class ImageDomainMixin:
    """图像生成相关方法。"""

    def generate_image(
        self,
        prompt: str,
        model: str = "image-01",
        n: int = 1,
        aspect_ratio: str = "1:1",
        width: int = 1024,
        height: int = 1024,
        style: dict = None,
        prompt_optimizer: bool = False,
        subject_reference: list = None,
        seed: int = None,
        watermark: bool = False,
        save_path: str = None,
    ) -> Dict[str, Any]:
        data = {
            "model": model,
            "prompt": prompt,
            "n": min(max(1, n), 9),
            "aspect_ratio": aspect_ratio,
            "response_format": "url",
            "prompt_optimizer": prompt_optimizer,
        }

        if style and model == "image-01-live":
            data["style"] = style
        if subject_reference:
            data["subject_reference"] = subject_reference
        if seed is not None:
            data["seed"] = seed
        if watermark:
            data["aigc_watermark"] = True

        result = self._post("/v1/image_generation", data)
        image_urls = result.get("data", {}).get("image_urls", [])
        saved_paths = []

        for i, url in enumerate(image_urls):
            if save_path:
                base_path = Path(save_path)
                if n > 1:
                    suffix = base_path.suffix or ".png"
                    path = base_path.with_name(f"{base_path.stem}_{i+1}{suffix}")
                else:
                    path = base_path
            else:
                path = self.output_dir / f"image_{int(time.time())}_{i+1}.png"

            try:
                img_data = self._download_url(url)
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(img_data)
                saved_paths.append(str(path))
            except Exception as e:
                saved_paths.append(f"下载失败: {e}")

        result["saved_paths"] = saved_paths
        return result
