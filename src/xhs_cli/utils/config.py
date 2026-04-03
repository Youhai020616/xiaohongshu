"""
全局配置管理 — ~/.xhs/config.json
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any

CONFIG_DIR = os.path.expanduser("~/.xhs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "mcp": {
        "host": "127.0.0.1",
        "port": 18060,
        "proxy": "",
        "auto_start": True,
    },
    "cdp": {
        "host": "127.0.0.1",
        "port": 9222,
        "headless": False,
    },
    "default": {
        "account": "default",
        "engine": "auto",  # auto | mcp | cdp
        "output": "table",  # table | json
    },
}


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config() -> dict[str, Any]:
    """加载配置文件，不存在则返回默认配置。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                user_cfg = json.load(f)
            # Merge with defaults
            merged = _deep_merge(DEFAULT_CONFIG, user_cfg)
            return merged
        except Exception as e:
            print(f"⚠️ 配置文件加载失败，使用默认配置: {e}", file=sys.stderr)
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict[str, Any]):
    """保存配置到文件。"""
    _ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get(key_path: str, default: Any = None) -> Any:
    """
    获取嵌套配置值。

    key_path 格式: "mcp.host", "default.engine"
    """
    cfg = load_config()
    keys = key_path.split(".")
    current = cfg
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def set_value(key_path: str, value: Any):
    """设置嵌套配置值。"""
    cfg = load_config()
    keys = key_path.split(".")
    current = cfg
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value
    save_config(cfg)


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典，使用 deepcopy 避免引用污染。"""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result
