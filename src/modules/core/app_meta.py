"""应用元信息加载（名称/版本等）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .paths import get_tool_dir

_DEFAULT_META = {
    "app_name": "MiniMaxAI",
    "display_name": "MiniMax AI 生成工具",
    "version": "0.0.1",
    "organization": "MiniMax",
}


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_tool_dir()


def _candidate_config_paths() -> list[Path]:
    paths = []
    env_path = os.environ.get("MINIMAX_APP_CONFIG", "").strip()
    if env_path:
        paths.append(Path(env_path))

    runtime_path = _runtime_base_dir() / "app_config.json"
    paths.append(runtime_path)

    tool_path = get_tool_dir() / "app_config.json"
    if tool_path != runtime_path:
        paths.append(tool_path)
    return paths


def get_app_meta() -> dict:
    meta = dict(_DEFAULT_META)
    for path in _candidate_config_paths():
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in _DEFAULT_META:
                value = str(data.get(key, "")).strip()
                if value:
                    meta[key] = value
            return meta
        except Exception:
            continue
    return meta
