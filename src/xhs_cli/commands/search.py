"""
xhs search / detail — 搜索和详情命令。
"""

from __future__ import annotations

import json

import click

from xhs_cli.engines.cdp_client import CDPClient, CDPError
from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.export import export_data
from xhs_cli.utils.index_cache import resolve_id, save_index
from xhs_cli.utils.output import (
    error,
    info,
    print_feed_detail,
    print_feeds,
    print_json,
    warning,
)


@click.command("search", help="搜索小红书笔记")
@click.argument("keyword")
@click.option(
    "--sort", type=click.Choice(["综合", "最新", "最多点赞", "最多评论", "最多收藏"]), default=None, help="排序方式"
)
@click.option("--type", "note_type", type=click.Choice(["不限", "视频", "图文"]), default=None, help="笔记类型")
@click.option(
    "--time", "pub_time", type=click.Choice(["不限", "一天内", "一周内", "半年内"]), default=None, help="发布时间"
)
@click.option("--scope", type=click.Choice(["不限", "已看过", "未看过", "已关注"]), default=None, help="搜索范围")
@click.option("--location", type=click.Choice(["不限", "同城", "附近"]), default=None, help="位置距离")
@click.option("--engine", type=click.Choice(["auto", "mcp", "cdp"]), default="auto", help="引擎 (cdp 返回推荐词)")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
@click.option("-o", "--output", default=None, help="导出到文件 (.json/.csv)")
@click.option("--limit", type=int, default=20, help="最大结果数")
def search(keyword, sort, note_type, pub_time, scope, location, engine, as_json, output, limit):
    """搜索笔记。搜索后可用 xhs read 1 / xhs like 1 操作结果。"""
    cfg = config.load_config()

    if engine == "auto":
        engine = cfg["default"].get("engine", "auto")
    if engine == "auto":
        engine = "mcp" if MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"]) else "cdp"

    if engine == "mcp":
        _search_mcp(cfg, keyword, sort, note_type, pub_time, scope, location, as_json, output, limit)
    else:
        if scope or location:
            warning("--scope 和 --location 仅 MCP 引擎支持，CDP 引擎将忽略")
        _search_cdp(cfg, keyword, sort, note_type, pub_time, as_json, output, limit)


def _search_mcp(cfg, keyword, sort, note_type, pub_time, scope, location, as_json, output, limit=20):
    client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])

    # 构建过滤条件描述用于日志
    filter_parts = []
    if sort:
        filter_parts.append(f"排序={sort}")
    if note_type:
        filter_parts.append(f"类型={note_type}")
    if pub_time:
        filter_parts.append(f"时间={pub_time}")
    if scope:
        filter_parts.append(f"范围={scope}")
    if location:
        filter_parts.append(f"位置={location}")
    filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""
    info(f"正在搜索: {keyword} (MCP{filter_desc})")

    try:
        # 构建 filters，字段名与 Go 端 FilterOption JSON tag 对齐
        filters = {}
        if sort:
            filters["sort_by"] = sort
        if note_type:
            filters["note_type"] = note_type
        if pub_time:
            filters["publish_time"] = pub_time
        if scope:
            filters["search_scope"] = scope
        if location:
            filters["location"] = location
        # 将 limit 加入 filters，由 MCP 服务端控制返回数量
        if limit:
            filters["limit"] = limit
        result = client.search(keyword, filters=filters or None)
    except MCPError as e:
        error(f"搜索失败: {e}")
        raise SystemExit(1)

    if as_json:
        print_json(result)
        return

    feeds = _extract_feeds(result)
    # 兜底：确保结果数不超过 limit
    feeds = feeds[:limit]

    # 缓存索引 — 支持 xhs read 1 / xhs like 1
    _cache_feeds(feeds)

    if output:
        export_data(feeds, output)
        return

    print_feeds(feeds, keyword=keyword)


def _search_cdp(cfg, keyword, sort, note_type, pub_time, as_json, output, limit=20):
    client = CDPClient(
        host=cfg["cdp"]["host"],
        port=cfg["cdp"]["port"],
        headless=True,
        reuse_tab=True,
    )

    info(f"正在搜索: {keyword} (CDP, 含推荐词)")

    try:
        result = client.search(
            keyword=keyword,
            sort_by=sort,
            note_type=note_type,
            publish_time=pub_time,
        )
    except CDPError as e:
        error(f"搜索失败: {e}")
        raise SystemExit(1)

    if as_json:
        print_json(result)
        return

    rec_keywords = result.get("recommended_keywords", [])
    if rec_keywords:
        kw_str = ", ".join(rec_keywords[:10])
        info(f"推荐关键词: {kw_str}")

    feeds = result.get("feeds", [])
    # 兜底：确保结果数不超过 limit
    feeds = feeds[:limit]
    _cache_feeds(feeds)

    if output:
        export_data(feeds, output)
        return

    print_feeds(feeds, keyword=keyword)


def _extract_feeds(result) -> list[dict]:
    if isinstance(result, dict):
        if "feeds" in result:
            return result["feeds"]
        content = result.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict) and "feeds" in parsed:
                            return parsed["feeds"]
                        if isinstance(parsed, list):
                            return parsed
                    except (json.JSONDecodeError, TypeError):
                        pass
    return []


def _cache_feeds(feeds: list[dict]):
    """缓存搜索结果供短索引使用。"""
    entries = []
    for feed in feeds:
        note_card = feed.get("noteCard", feed.get("note_card", feed))
        note_id = feed.get("id") or feed.get("note_id") or ""
        token = feed.get("xsecToken") or feed.get("xsec_token") or ""
        if note_id:
            entries.append(
                {
                    "note_id": note_id,
                    "xsec_token": token,
                    "desc": (note_card.get("displayTitle") or note_card.get("display_title") or "")[:40],
                    "author": (
                        note_card.get("user", {}).get("nickname") or note_card.get("user", {}).get("nickName") or ""
                    ),
                }
            )
    save_index(entries)


@click.command("detail", help="查看笔记详情 (支持短索引: xhs detail 1)")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token (短索引自动填入)")
@click.option("--comments", is_flag=True, help="加载全部评论 (默认仅前 10 条)")
@click.option("--comment-limit", type=int, default=20, help="最多加载评论数 (默认 20，需 --comments)")
@click.option("--expand-replies", is_flag=True, help="展开子评论/二级回复 (需 --comments)")
@click.option("--reply-limit", type=int, default=10, help="跳过回复数超过此值的评论 (默认 10，需 --expand-replies)")
@click.option(
    "--scroll-speed",
    type=click.Choice(["slow", "normal", "fast"]),
    default=None,
    help="评论滚动加载速度 (需 --comments)",
)
@click.option("--engine", type=click.Choice(["auto", "mcp", "cdp"]), default="auto")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def detail(feed_id, token, comments, comment_limit, expand_replies, reply_limit, scroll_speed, engine, as_json):
    """查看笔记详情和评论。支持短索引 (xhs search → xhs detail 1)。"""
    # 解析短索引
    try:
        resolved = resolve_id(feed_id)
    except ValueError as e:
        error(str(e))
        raise SystemExit(1)

    # 从缓存获取 token
    if resolved != feed_id:
        from xhs_cli.utils.index_cache import get_by_index

        entry = get_by_index(int(feed_id))
        if entry and not token:
            token = entry.get("xsec_token", "")
        feed_id = resolved

    if not token:
        error("需要 xsec_token，请使用 -t TOKEN 或通过搜索后用短索引访问")
        raise SystemExit(1)

    cfg = config.load_config()
    # 先检查配置偏好，与 search 命令保持一致
    if engine == "auto":
        engine = cfg["default"].get("engine", "auto")
    if engine == "auto":
        engine = "mcp" if MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"]) else "cdp"

    try:
        if engine == "mcp":
            client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
            info("正在获取详情 (MCP)...")
            result = client.get_feed_detail(
                feed_id,
                token,
                load_all_comments=comments,
                limit=comment_limit,
                click_more_replies=expand_replies,
                reply_limit=reply_limit,
                scroll_speed=scroll_speed,
            )
        else:
            client = CDPClient(
                host=cfg["cdp"]["host"],
                port=cfg["cdp"]["port"],
                headless=True,
                reuse_tab=True,
            )
            info("正在获取详情 (CDP)...")
            result = client.get_feed_detail(feed_id, token)
    except (MCPError, CDPError) as e:
        error(f"获取详情失败: {e}")
        raise SystemExit(1)

    if as_json:
        print_json(result)
    else:
        print_feed_detail(result)
