"""按领域拆分的 API 能力。"""

from .speech import SpeechDomainMixin
from .image import ImageDomainMixin
from .video import VideoDomainMixin
from .music import MusicDomainMixin
from .chat import ChatDomainMixin

__all__ = [
    "SpeechDomainMixin",
    "ImageDomainMixin",
    "VideoDomainMixin",
    "MusicDomainMixin",
    "ChatDomainMixin",
]

