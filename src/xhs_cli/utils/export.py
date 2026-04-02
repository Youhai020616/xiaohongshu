"""
导出工具 — 将列表数据导出为 JSON / CSV 文件。
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any

from xhs_cli.utils.output import success


def export_data(data: list[dict], output_path: str) -> None:
    """根据文件扩展名导出数据。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".csv":
        _export_csv(data, output_path)
    elif ext in (".json", ".jsonl"):
        _export_json(data, output_path)
    elif ext in (".yaml", ".yml"):
        _export_yaml(data, output_path)
    else:
        _export_json(data, output_path)

    success(f"已导出 {len(data)} 条到 {output_path}")


def _export_json(data: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _export_csv(data: list[dict], path: str) -> None:
    if not data:
        return
    # Flatten nested dicts for CSV
    flat = [_flatten(item) for item in data]
    keys = list(flat[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)


def _export_yaml(data: list[dict], path: str) -> None:
    try:
        import yaml

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    except ImportError:
        _export_json(data, path)


def _flatten(d: dict, prefix: str = "") -> dict:
    """将嵌套 dict 展平为单层 (用于 CSV)。"""
    items: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten(v, key))
        elif isinstance(v, list):
            items[key] = str(v)[:100]
        else:
            items[key] = v
    return items
