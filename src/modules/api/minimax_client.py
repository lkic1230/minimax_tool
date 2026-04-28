"""MiniMax 客户端聚合入口。"""
from enum import Enum

from .base_client import BaseMiniMaxClient
from ..core.constants import (
    SPEECH_MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    MUSIC_MODEL_DEFAULT,
    MUSIC_COVER_MODEL_DEFAULT,
)
from .domains import (
    ChatDomainMixin,
    ImageDomainMixin,
    MusicDomainMixin,
    SpeechDomainMixin,
    VideoDomainMixin,
)


class ModelType(Enum):
    """支持的模型类型（预留供将来使用）。"""

    SPEECH_28_HD = SPEECH_MODELS[0]
    SPEECH_28_TURBO = SPEECH_MODELS[1]
    SPEECH_26_HD = SPEECH_MODELS[2]
    SPEECH_26_TURBO = SPEECH_MODELS[3]
    SPEECH_02_HD = "speech-02-hd"
    SPEECH_02_TURBO = "speech-02-turbo"

    IMAGE_01 = IMAGE_MODELS[0]
    IMAGE_01_LIVE = IMAGE_MODELS[1]

    HAILUO_23 = VIDEO_MODELS[0]
    HAILUO_23_FAST = VIDEO_MODELS[2]
    HAILUO_02 = VIDEO_MODELS[1]
    VIDEO_T2V_01 = "T2V-01"
    VIDEO_T2V_01_DIRECTOR = "T2V-01-Director"
    VIDEO_I2V_01 = "I2V-01"
    VIDEO_I2V_01_LIVE = "I2V-01-live"
    VIDEO_I2V_01_DIRECTOR = "I2V-01-Director"

    MUSIC_26 = MUSIC_MODEL_DEFAULT
    MUSIC_COVER = MUSIC_COVER_MODEL_DEFAULT


class MiniMaxClient(
    SpeechDomainMixin,
    ImageDomainMixin,
    VideoDomainMixin,
    MusicDomainMixin,
    ChatDomainMixin,
    BaseMiniMaxClient,
):
    """MiniMax API 客户端（聚合各领域能力）。"""
