"""Tests for xhs_cli.utils.index_cache"""

from __future__ import annotations

import pytest

from xhs_cli.utils import index_cache


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    cache_file = str(tmp_path / "index_cache.json")
    monkeypatch.setattr(index_cache, "INDEX_FILE", cache_file)


class TestSaveAndGet:
    def test_save_and_get(self):
        items: list[dict] = [
            {"note_id": "aaa", "desc": "note one", "author": {"nickname": "alice"}},
            {"note_id": "bbb", "desc": "note two", "author": {"nickname": "bob"}},
        ]
        index_cache.save_index(items)  # type: ignore[arg-type]
        entry1 = index_cache.get_by_index(1)
        entry2 = index_cache.get_by_index(2)
        assert entry1 is not None
        assert entry2 is not None
        assert entry1["note_id"] == "aaa"
        assert entry2["note_id"] == "bbb"

    def test_xsec_token_preserved(self):
        """xsec_token 必须被正确保存和读取，否则短索引互动链路断裂。"""
        items: list[dict] = [
            {"note_id": "aaa", "xsec_token": "token_abc", "desc": "note", "author": "alice"},
            {"note_id": "bbb", "xsec_token": "token_xyz", "desc": "note2", "author": "bob"},
            {"note_id": "ccc", "desc": "no token", "author": "carol"},
        ]
        index_cache.save_index(items)  # type: ignore[arg-type]
        entry1 = index_cache.get_by_index(1)
        entry2 = index_cache.get_by_index(2)
        entry3 = index_cache.get_by_index(3)
        assert entry1 is not None and entry1["xsec_token"] == "token_abc"
        assert entry2 is not None and entry2["xsec_token"] == "token_xyz"
        assert entry3 is not None and entry3["xsec_token"] == ""

    def test_out_of_range(self):
        index_cache.save_index([{"note_id": "x", "desc": "", "author": "u"}])  # type: ignore[arg-type]
        assert index_cache.get_by_index(5) is None

    def test_empty(self):
        assert index_cache.get_by_index(1) is None
        assert index_cache.get_index_count() == 0

    def test_count(self):
        index_cache.save_index([{"note_id": str(i), "desc": "", "author": "u"} for i in range(5)])
        assert index_cache.get_index_count() == 5


class TestResolveId:
    def test_long_id(self):
        assert index_cache.resolve_id("6789abcdef123456") == "6789abcdef123456"

    def test_url(self):
        url = "https://www.xiaohongshu.com/explore/xxx"
        assert index_cache.resolve_id(url) == url

    def test_short_index(self):
        index_cache.save_index([{"note_id": "abc123", "desc": "", "author": "u"}])
        assert index_cache.resolve_id("1") == "abc123"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="请先执行"):
            index_cache.resolve_id("1")
