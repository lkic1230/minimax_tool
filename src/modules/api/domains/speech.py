"""语音领域 API。"""
import time
from pathlib import Path
from typing import Any, Dict, List


class SpeechDomainMixin:
    """语音生成相关方法。"""

    def generate_speech(
        self,
        text: str,
        model: str = "speech-2.8-hd",
        voice_id: str = "female-tianmei",
        speed: float = 1.0,
        volume: float = 1.0,
        pitch: float = 1.0,
        emotion: str = "neutral",
        output_format: str = "url",
        save_path: str = None,
    ) -> Dict[str, Any]:
        data = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": volume,
                "pitch": pitch,
                "emotion": emotion,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
            "output_format": output_format,
        }

        result = self._post("/v1/t2a_v2", data)

        if save_path:
            save_path = Path(save_path)
        else:
            save_path = self.output_dir / f"speech_{int(time.time())}.mp3"

        if result.get("data", {}).get("audio"):
            audio_data = result["data"]["audio"]
            if output_format == "hex":
                audio_bytes = bytes.fromhex(audio_data)
            else:
                audio_bytes = self._download_url(audio_data)

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(audio_bytes)
            result["saved_path"] = str(save_path)

        return result

    def list_voices(self) -> List[Dict[str, str]]:
        return [
            {"id": "female-tianmei", "name": "甜妹", "gender": "female"},
            {"id": "female-yuanzi", "name": "元气少女", "gender": "female"},
            {"id": "female-susanna", "name": "苏珊娜", "gender": "female"},
            {"id": "male-yuanbao", "name": "元宝", "gender": "male"},
            {"id": "male-hongren", "name": "浩然", "gender": "male"},
            {"id": "male-john", "name": "约翰", "gender": "male"},
            {"id": "male-tianmei", "name": "甜帅哥", "gender": "male"},
        ]

