from .chat_tab import ChatTabWidget
from .speech_tab import SpeechTabWidget
from .config_tab import ConfigTabWidget
from .image_tab import ImageTabWidget
from .video_tab import VideoTabWidget
from .music_tab import MusicTabWidget
from .agent_tab import AgentTabWidget
from .agent_chat_tab import AgentChatTabWidget
from .agent_enhanced_chat import AgentChatTabWidget as EnhancedChatTabWidget

__all__ = [
    "ChatTabWidget",
    "SpeechTabWidget",
    "ConfigTabWidget",
    "ImageTabWidget",
    "VideoTabWidget",
    "MusicTabWidget",
    "AgentTabWidget",
    "AgentChatTabWidget",
    "EnhancedChatTabWidget",
]
