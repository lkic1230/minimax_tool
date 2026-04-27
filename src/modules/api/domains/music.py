"""音乐领域 API。"""
import time
from pathlib import Path
from typing import Any, Dict


class MusicDomainMixin:
    """音乐生成相关方法。"""

    def generate_music(
        self,
        prompt: str,
        model: str = "music-2.6",
        lyrics: str = None,
        is_instrumental: bool = False,
        audio_url: str = None,
        audio_base64: str = None,
        cover_feature_id: str = None,
        lyrics_optimizer: bool = False,
        output_format: str = "url",
        save_path: str = None,
    ) -> Dict[str, Any]:
        if model not in ["music-2.6", "music-cover", "music-2.6-free", "music-cover-free"]:
            raise ValueError(f"不支持的模型: {model}，可选: music-2.6, music-cover, music-2.6-free, music-cover-free")

        if not prompt:
            raise ValueError("prompt 不能为空")
        if len(prompt) > 2000:
            raise ValueError(f"prompt 长度不能超过 2000 字符，当前: {len(prompt)}")

        if model in ["music-cover", "music-cover-free"] and len(prompt) < 10:
            raise ValueError(f"music-cover 模式的 prompt 长度不能少于 10 字符，当前: {len(prompt)}")

        data = {
            "model": model,
            "prompt": prompt,
            "output_format": output_format,
            "is_instrumental": is_instrumental,
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": "mp3",
            },
        }

        if lyrics:
            if len(lyrics) > 3500:
                raise ValueError(f"lyrics 长度不能超过 3500 字符，当前: {len(lyrics)}")
            data["lyrics"] = lyrics

        if lyrics_optimizer and model in ["music-2.6", "music-2.6-free"]:
            data["lyrics_optimizer"] = True

        if model in ["music-2.6", "music-2.6-free"] and not is_instrumental and not lyrics and not lyrics_optimizer:
            raise ValueError("music-2.6/music-2.6-free 非纯音乐模式需要提供 lyrics 参数，或设置 lyrics_optimizer=true 自动生成")

        if model in ["music-cover", "music-cover-free"]:
            if cover_feature_id:
                data["cover_feature_id"] = cover_feature_id
            elif audio_url:
                data["audio_url"] = audio_url
            elif audio_base64:
                data["audio_base64"] = audio_base64
            else:
                raise ValueError("music-cover 模式需要提供 audio_url、cover_feature_id 或 audio_base64")

        if model in ["music-cover", "music-cover-free"] and lyrics:
            if len(lyrics) < 10 or len(lyrics) > 1000:
                raise ValueError(f"music-cover 模式的 lyrics 长度需在 10-1000 字符，当前: {len(lyrics)}")

        result = self._post("/v1/music_generation", data, timeout=300)

        if save_path:
            save_path = Path(save_path)
        else:
            save_path = self.output_dir / f"music_{int(time.time())}.mp3"

        audio_data = result.get("data", {}).get("audio")
        if audio_data:
            if output_format == "hex":
                audio_bytes = bytes.fromhex(audio_data)
            else:
                audio_bytes = self._download_url(audio_data)

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(audio_bytes)
            result["saved_path"] = str(save_path)

        return result

    def cover_preprocess(
        self,
        audio_url: str = None,
        audio_base64: str = None,
        model: str = "music-cover",
    ) -> Dict[str, Any]:
        if model != "music-cover":
            raise ValueError("cover_preprocess 只支持 music-cover 模型")
        if not audio_url and not audio_base64:
            raise ValueError("需要提供 audio_url 或 audio_base64")
        if audio_url and audio_base64:
            raise ValueError("audio_url 和 audio_base64 只能提供其中一个")

        data = {"model": model}
        if audio_url:
            data["audio_url"] = audio_url
        else:
            data["audio_base64"] = audio_base64

        return self._post("/v1/music_cover_preprocess", data, timeout=120)

    def generate_lyrics(
        self,
        mode: str = "write_full_song",
        prompt: str = None,
        lyrics: str = None,
        title: str = None,
    ) -> Dict[str, Any]:
        if mode not in ["write_full_song", "edit"]:
            raise ValueError("mode 必须为 write_full_song 或 edit")
        if prompt and len(prompt) > 2000:
            raise ValueError(f"prompt 长度不能超过 2000，当前: {len(prompt)}")
        if lyrics and len(lyrics) > 3500:
            raise ValueError(f"lyrics 长度不能超过 3500，当前: {len(lyrics)}")

        data = {"mode": mode}
        if prompt:
            data["prompt"] = prompt
        if lyrics:
            data["lyrics"] = lyrics
        if title:
            data["title"] = title
        return self._post("/v1/lyrics_generation", data, timeout=60)

