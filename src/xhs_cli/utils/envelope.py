"""
统一输出信封 — Agent 友好的结构化输出。

所有 --json / --yaml 输出使用此信封格式:
  成功: {ok: true, schema_version: "1", data: ...}
  失败: {ok: false, schema_version: "1", error: {code: ..., message: ...}}
"""
from __future__ import annotations

import json
import sys
from typing import Any

SCHEMA_VERSION = "1"


def success_envelope(data: Any) -> dict:
    return {"ok": True, "schema_version": SCHEMA_VERSION, "data": data}


def error_envelope(code: str, message: str) -> dict:
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "error": {"code": code, "message": message},
    }


def emit(envelope: dict, fmt: str = "auto") -> None:
    """输出信封到 stdout。

    fmt: "json" | "yaml" | "auto"
    auto: TTY → 不输出(由 Rich 处理), 非 TTY → yaml
    """
    if fmt == "auto":
        if not sys.stdout.isatty():
            fmt = "yaml"
        else:
            return  # TTY 模式由 Rich 处理

    if fmt == "yaml":
        try:
            import yaml
            sys.stdout.write(yaml.dump(envelope, allow_unicode=True, default_flow_style=False, sort_keys=False))
        except ImportError:
            # fallback to json if pyyaml not installed
            sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
