"""
短索引导航 — 列表命令自动缓存结果，后续命令用数字引用。

用法:
  xhs search "美食"     →  缓存搜索结果
  dy read 1            →  读取第 1 条
  dy download 3        →  下载第 3 条
  dy detail 2          →  查看第 2 条详情
"""

from __future__ import annotations

import json
import os
from typing import Any

CONFIG_DIR = os.path.expanduser("~/.xhs")

INDEX_FILE = os.path.join(CONFIG_DIR, "index_cache.json")


def save_index(items: list[dict[str, Any]]) -> None:
    """保存列表结果的索引。每条记录需要 note_id。"""
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    entries = []
    for item in items:
        note_id = item.get("note_id", "")
        if note_id:
            entries.append(
                {
                    "note_id": str(note_id),
                    "xsec_token": item.get("xsec_token", ""),
                    "desc": item.get("desc", "")[:60],
                    "author": item.get("author", {}).get("nickname", "")
                    if isinstance(item.get("author"), dict)
                    else str(item.get("author", "")),
                    "sec_uid": item.get("author", {}).get("sec_uid", "")
                    if isinstance(item.get("author"), dict)
                    else "",
                }
            )
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def get_by_index(index: int) -> dict[str, str] | None:
    """用 1-based 索引获取缓存条目。"""
    if index <= 0:
        return None
    if not os.path.isfile(INDEX_FILE):
        return None
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or index > len(data):
            return None
        return data[index - 1]
    except (json.JSONDecodeError, OSError):
        return None


def resolve_id(id_or_index: str) -> str:
    """解析 note_id: 短数字(≤999)视为索引，长数字视为 ID，含字母/URL 原样返回。"""
    if not id_or_index.isdigit():
        return id_or_index

    n = int(id_or_index)
    # 短索引: 1-999; note_id 通常 > 15 位
    if n <= 999:
        entry = get_by_index(n)
        if entry:
            return entry["note_id"]
        # 索引不存在时给出明确提示，不要把 "1" 当 note_id
        count = get_index_count()
        if count == 0:
            raise ValueError("没有缓存的搜索结果，请先执行 xhs search")
        raise ValueError(f"索引 {n} 超出范围 (共 {count} 条)")

    return id_or_index


def get_index_count() -> int:
    """获取缓存的条目数量。"""
    if not os.path.isfile(INDEX_FILE):
        return 0
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError):
        return 0
