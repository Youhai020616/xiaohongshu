"""
xhs like / comment / favorite / reply / follow — 互动命令 (支持短索引)。
"""
from __future__ import annotations

import click

from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.index_cache import get_by_index, resolve_id
from xhs_cli.utils.output import error, info, success


def _resolve_feed(feed_id_or_index: str, token: str = ""):
    """解析 feed_id 和 token (支持短索引)。"""
    try:
        resolved = resolve_id(feed_id_or_index)
    except ValueError as e:
        error(str(e))
        raise SystemExit(1)

    if resolved != feed_id_or_index and not token:
        entry = get_by_index(int(feed_id_or_index))
        if entry:
            token = entry.get("xsec_token", "")

    if not token:
        error("需要 xsec_token，请使用 -t TOKEN 或通过搜索后用短索引")
        raise SystemExit(1)

    return resolved, token


def _get_mcp():
    cfg = config.load_config()
    return MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])


def _extract_result_text(result) -> str:
    """从 MCP 工具返回值中提取文本。

    MCP 结果格式可能是：
    - {"content": [{"type": "text", "text": "..."}]}  (标准 MCP)
    - {"result": {"content": [...]}}                   (JSON-RPC 包装)
    - str                                              (直接字符串)
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        # 尝试从 content 数组提取
        content = result.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            if parts:
                return "\n".join(parts)
        # 直接取 text
        if "text" in result:
            return result["text"]
        # 嵌套 result
        if "result" in result:
            return _extract_result_text(result["result"])
    return str(result)


@click.command("like", help="点赞笔记 (支持短索引: xhs like 1)")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--unlike", is_flag=True, help="取消点赞")
def like(feed_id, token, unlike):
    """点赞或取消点赞。"""
    feed_id, token = _resolve_feed(feed_id, token or "")
    action = "取消点赞" if unlike else "点赞"
    info(f"正在{action}...")

    try:
        result = _get_mcp().like(feed_id, token, unlike=unlike)
        text = _extract_result_text(result)
        # Go 端已有智能检测：已点赞则跳过点击，返回文本包含结果
        if "失败" in text:
            error(text)
            raise SystemExit(1)
        success(f"{action}成功 👍")
        if text:
            info(f"服务端: {text}")
    except MCPError as e:
        error(f"{action}失败: {e}")
        raise SystemExit(1)


@click.command("favorite", help="收藏笔记 (支持短索引: xhs fav 1)")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--unfavorite", is_flag=True, help="取消收藏")
def favorite(feed_id, token, unfavorite):
    """收藏或取消收藏。"""
    feed_id, token = _resolve_feed(feed_id, token or "")
    action = "取消收藏" if unfavorite else "收藏"
    info(f"正在{action}...")

    try:
        result = _get_mcp().favorite(feed_id, token, unfavorite=unfavorite)
        text = _extract_result_text(result)
        if "失败" in text:
            error(text)
            raise SystemExit(1)
        success(f"{action}成功 ⭐")
        if text:
            info(f"服务端: {text}")
    except MCPError as e:
        error(f"{action}失败: {e}")
        raise SystemExit(1)


@click.command("comment", help="评论笔记 (支持短索引: xhs comment 1 -c '好文')")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--content", "-c", required=True, help="评论内容")
def comment(feed_id, token, content):
    """发表评论。"""
    feed_id, token = _resolve_feed(feed_id, token or "")
    info("正在发表评论...")

    try:
        result = _get_mcp().comment(feed_id, token, content)
        text = _extract_result_text(result)
        if "失败" in text:
            error(text)
            raise SystemExit(1)
        success("评论成功 💬")
        if text:
            info(f"服务端: {text}")
    except MCPError as e:
        error(f"评论失败: {e}")
        raise SystemExit(1)


@click.command("reply", help="回复评论 (支持短索引)")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--comment-id", required=True, help="评论 ID")
@click.option("--user-id", required=True, help="被回复用户 ID")
@click.option("--content", "-c", required=True, help="回复内容")
def reply(feed_id, token, comment_id, user_id, content):
    """回复某条评论。"""
    feed_id, token = _resolve_feed(feed_id, token or "")
    info("正在回复...")

    try:
        result = _get_mcp().reply(feed_id, token, comment_id, user_id, content)
        text = _extract_result_text(result)
        if "失败" in text:
            error(text)
            raise SystemExit(1)
        success("回复成功 💬")
        if text:
            info(f"服务端: {text}")
    except MCPError as e:
        error(f"回复失败: {e}")
        raise SystemExit(1)


@click.command("feeds", help="获取首页推荐")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def feeds(as_json):
    """获取首页推荐 Feed。"""
    import json as json_mod

    from xhs_cli.utils.output import print_feeds, print_json

    client = _get_mcp()
    info("正在获取首页推荐...")

    try:
        result = client.list_feeds()
        if as_json:
            print_json(result)
        else:
            feed_list = []
            if isinstance(result, dict):
                content = result.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            try:
                                parsed = json_mod.loads(item.get("text", ""))
                                if isinstance(parsed, list):
                                    feed_list = parsed
                                elif isinstance(parsed, dict) and "feeds" in parsed:
                                    feed_list = parsed["feeds"]
                            except Exception:
                                pass
            print_feeds(feed_list, keyword="首页推荐")
    except MCPError as e:
        error(f"获取推荐失败: {e}")
        raise SystemExit(1)
