"""
路径管理模块 - 统一管理工具相关的目录路径
"""
import os
from pathlib import Path


def get_tool_dir() -> Path:
    """获取工具根目录（主要用于源码场景）。"""
    env_dir = os.environ.get("MINIMAX_TOOL_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if parent.name == "minimax_tool":
            return parent

    if current_file.parent.name == "minimax_tool":
        return current_file.parent

    return Path.cwd()


def get_config_home() -> Path:
    """获取配置存储目录（AppData 或 Home）。"""
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "minimax_tool"
    return Path(os.path.expanduser("~")) / ".minimax_tool"


def _get_data_root() -> Path:
    """
    获取运行时数据根目录。
    优先 MINIMAX_TOOL_DIR 环境变量 → 工具自身目录 → 用户配置目录。
    """
    env_dir = os.environ.get("MINIMAX_TOOL_DIR")
    if env_dir:
        return Path(env_dir)

    tool_dir = get_tool_dir()
    # 工具目录存在且可写时，优先使用工具自身目录存放数据
    try:
        (tool_dir / "outputs").mkdir(parents=True, exist_ok=True)
        return tool_dir
    except OSError:
        return get_config_home()


def get_outputs_dir() -> Path:
    """获取输出目录（默认）。"""
    return _get_data_root() / "outputs"


def get_cache_dir() -> Path:
    """获取缓存目录。"""
    return _get_data_root() / "cache"


def ensure_dirs():
    """确保必要的目录存在。"""
    get_outputs_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
