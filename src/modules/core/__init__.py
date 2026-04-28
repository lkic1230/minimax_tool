"""核心基础设施模块。"""

from .paths import (
    get_tool_dir,
    get_outputs_dir,
    get_cache_dir,
    get_config_home,
    ensure_dirs,
)
from .config_manager import ConfigManager, get_config_manager
from .constants import (
    CHAT_MODEL_DEFAULT,
    CHAT_MAX_TOKENS_MIN,
    CHAT_MAX_TOKENS_MAX,
    CHAT_MAX_TOKENS_DEFAULT,
    CHAT_TEMPERATURE_MIN,
    CHAT_TEMPERATURE_MAX,
    CHAT_TEMPERATURE_DEFAULT,
    CHAT_TOP_P_MIN,
    CHAT_TOP_P_MAX,
    CHAT_TOP_P_DEFAULT,
    CHAT_SAMPLING_PRESETS,
    CHAT_SAMPLING_CUSTOM_LABEL,
)

__all__ = [
    "get_tool_dir",
    "get_outputs_dir",
    "get_cache_dir",
    "get_config_home",
    "ensure_dirs",
    "ConfigManager",
    "get_config_manager",
    "CHAT_MODEL_DEFAULT",
    "CHAT_MAX_TOKENS_MIN",
    "CHAT_MAX_TOKENS_MAX",
    "CHAT_MAX_TOKENS_DEFAULT",
    "CHAT_TEMPERATURE_MIN",
    "CHAT_TEMPERATURE_MAX",
    "CHAT_TEMPERATURE_DEFAULT",
    "CHAT_TOP_P_MIN",
    "CHAT_TOP_P_MAX",
    "CHAT_TOP_P_DEFAULT",
    "CHAT_SAMPLING_PRESETS",
    "CHAT_SAMPLING_CUSTOM_LABEL",
]
