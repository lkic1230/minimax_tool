"""语音领域 API。"""
import time
from pathlib import Path
from typing import Any, Dict, List

from ...core.constants import (
    SPEECH_MODELS,
    SPEECH_MODEL_DEFAULT,
    SPEECH_VOICES,
    SPEECH_VOICE_DEFAULT,
    SPEECH_API_EMOTIONS,
    SPEECH_EMOTION_DEFAULT,
    SPEECH_SPEED_MIN,
    SPEECH_SPEED_MAX,
    SPEECH_SPEED_DEFAULT,
)


class SpeechDomainMixin:
    """语音生成相关方法。"""

    def generate_speech(
        self,
        text: str,
        model: str = SPEECH_MODEL_DEFAULT,
        voice_id: str = SPEECH_VOICE_DEFAULT,
        speed: float = SPEECH_SPEED_DEFAULT,
        volume: float = 1.0,
        pitch: float = 1.0,
        emotion: str = SPEECH_EMOTION_DEFAULT,
        output_format: str = "url",
        save_path: str = None,
    ) -> Dict[str, Any]:
        if model not in SPEECH_MODELS:
            raise ValueError(f"不支持的语音模型: {model}，可选: {', '.join(SPEECH_MODELS)}")
        if voice_id not in SPEECH_VOICES:
            raise ValueError(f"不支持的音色: {voice_id}，可选: {', '.join(SPEECH_VOICES)}")
        if not (SPEECH_SPEED_MIN <= speed <= SPEECH_SPEED_MAX):
            raise ValueError(f"语速超出范围: {speed}，应在 {SPEECH_SPEED_MIN}-{SPEECH_SPEED_MAX}")
        if emotion not in SPEECH_API_EMOTIONS:
            raise ValueError(f"不支持的情感: {emotion}，可选: {', '.join(SPEECH_API_EMOTIONS)}")

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
