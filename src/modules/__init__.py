"""MiniMax 功能模块。"""

from .ui.components.common import GenerationThread, AudioPlayer
from .ui.tabs.chat_tab import ChatTabWidget
from .ui.tabs.speech_tab import SpeechTabWidget
from .ui.tabs.config_tab import ConfigTabWidget
from .ui.tabs.image_tab import ImageTabWidget
from .ui.tabs.video_tab import VideoTabWidget
from .ui.tabs.music_tab import MusicTabWidget

__all__ = [
    "GenerationThread",
    "AudioPlayer",
    "ChatTabWidget",
    "SpeechTabWidget",
    "ConfigTabWidget",
    "ImageTabWidget",
    "VideoTabWidget",
    "MusicTabWidget",
]
