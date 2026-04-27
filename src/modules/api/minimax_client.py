"""MiniMax 客户端聚合入口。"""
from enum import Enum

from .base_client import BaseMiniMaxClient
from .domains import (
    ChatDomainMixin,
    ImageDomainMixin,
    MusicDomainMixin,
    SpeechDomainMixin,
    VideoDomainMixin,
)


class ModelType(Enum):
    """支持的模型类型（预留供将来使用）。"""

    SPEECH_28_HD = "speech-2.8-hd"
    SPEECH_28_TURBO = "speech-2.8-turbo"
    SPEECH_26_HD = "speech-2.6-hd"
    SPEECH_26_TURBO = "speech-2.6-turbo"
    SPEECH_02_HD = "speech-02-hd"
    SPEECH_02_TURBO = "speech-02-turbo"

    IMAGE_01 = "image-01"
    IMAGE_01_LIVE = "image-01-live"

    HAILUO_23 = "MiniMax-Hailuo-2.3"
    HAILUO_23_FAST = "MiniMax-Hailuo-2.3-Fast"
    HAILUO_02 = "MiniMax-Hailuo-02"
    VIDEO_T2V_01 = "T2V-01"
    VIDEO_T2V_01_DIRECTOR = "T2V-01-Director"
    VIDEO_I2V_01 = "I2V-01"
    VIDEO_I2V_01_LIVE = "I2V-01-live"
    VIDEO_I2V_01_DIRECTOR = "I2V-01-Director"

    MUSIC_26 = "music-2.6"
    MUSIC_COVER = "music-cover"


class MiniMaxClient(
    SpeechDomainMixin,
    ImageDomainMixin,
    VideoDomainMixin,
    MusicDomainMixin,
    ChatDomainMixin,
    BaseMiniMaxClient,
):
    """MiniMax API 客户端（聚合各领域能力）。"""

