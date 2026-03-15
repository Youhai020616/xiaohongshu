"""
统一输出格式化 — 表格、JSON、状态信息。
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()
err_console = Console(stderr=True)


def success(msg: str):
    """打印成功信息。"""
    console.print(f"[bold green]✓[/] {msg}")


def error(msg: str):
    """打印错误信息。"""
    err_console.print(f"[bold red]✗[/] {msg}")


def warning(msg: str):
    """打印警告信息。"""
    console.print(f"[bold yellow]⚠[/] {msg}")


def info(msg: str):
    """打印普通信息。"""
    console.print(f"[dim]ℹ[/] {msg}")


def status(label: str, value: str, style: str = ""):
    """打印键值对状态。"""
    if style:
        console.print(f"  [bold]{label}:[/] [{style}]{value}[/]")
    else:
        console.print(f"  [bold]{label}:[/] {value}")


def print_json(data: Any, envelope: bool = True):
    """打印格式化 JSON（统一信封格式）。"""
    from xhs_cli.utils.envelope import success_envelope
    output = success_envelope(data) if envelope else data
    console.print_json(json.dumps(output, ensure_ascii=False, indent=2))


def print_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
    max_width: int | None = None,
):
    """打印 Rich 表格。"""
    table = Table(title=title, box=box.ROUNDED, show_lines=True, expand=False)
    for col in columns:
        table.add_column(col, overflow="fold", max_width=max_width or 40)
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


def print_feeds(feeds: list[dict], keyword: str = ""):
    """打印搜索结果列表。"""
    # 过滤掉非笔记类型 (如 rec_query 推荐词条目)
    real_feeds = [f for f in feeds if _get_nested(f, "modelType", "") != "rec_query"
                  and _get_nested(f, "noteCard.displayTitle", _get_nested(f, "note_card.display_title", ""))]

    if not real_feeds:
        warning("未找到相关笔记")
        return

    title = f"搜索结果: {keyword} ({len(real_feeds)} 条)" if keyword else f"笔记列表 ({len(real_feeds)} 条)"
    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("标题", max_width=30, overflow="fold")
    table.add_column("作者", max_width=12, overflow="fold")
    table.add_column("点赞", justify="right", width=8)
    table.add_column("类型", width=6)
    table.add_column("Feed ID", style="dim", max_width=26)
    table.add_column("Token", style="dim", max_width=20, overflow="ellipsis")

    for i, feed in enumerate(real_feeds, 1):
        # 支持驼峰 (MCP) 和蛇形 (CDP) 两种命名
        note_card = feed.get("noteCard", feed.get("note_card", feed))
        user = note_card.get("user", {})
        interact = note_card.get("interactInfo", note_card.get("interact_info", {}))

        title_text = (note_card.get("displayTitle")
                      or note_card.get("display_title")
                      or note_card.get("title")
                      or "-")
        author = user.get("nickname") or user.get("nickName") or user.get("nick_name") or "-"
        likes = _first_valid(interact, "likedCount", "liked_count")
        note_type = "视频" if note_card.get("type") == "video" else "图文"
        feed_id = feed.get("id") or feed.get("note_id") or "-"
        token = feed.get("xsecToken") or feed.get("xsec_token") or ""

        table.add_row(str(i), title_text, author, str(likes), note_type, feed_id, token[:18] + "…" if len(token) > 18 else token)

    console.print(table)


def _first_valid(d: dict, *keys, default: str = "-") -> str:
    """从字典中取第一个非 None 的值（安全处理 0 和空字符串）。"""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return str(v)
    return default


def _get_nested(d: dict, key_path: str, default: Any = None) -> Any:
    """获取嵌套字典值，支持 'a.b.c' 路径。"""
    keys = key_path.split(".")
    current = d
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def print_feed_detail(detail: dict):
    """打印笔记详情（兼容 MCP 嵌套 JSON 格式）。"""
    # 检查 isError
    if detail.get("isError"):
        error_text = ""
        for item in detail.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                error_text = item.get("text", "")
        error(f"获取详情失败: {error_text}")
        return

    # MCP 返回 content[0].text 是嵌套 JSON
    parsed = _unwrap_mcp_text(detail)
    note = (parsed.get("data", {}).get("note", {})
            or parsed.get("detail", parsed).get("note_card", parsed.get("detail", parsed)))

    title = note.get("title") or note.get("displayTitle") or note.get("display_title") or "笔记详情"
    content = note.get("desc") or note.get("content") or ""
    user = note.get("user", {})
    interact = note.get("interactInfo", note.get("interact_info", {}))

    nickname = user.get("nickname") or user.get("nickName") or "-"
    likes = _first_valid(interact, "likedCount", "liked_count")
    collects = _first_valid(interact, "collectedCount", "collected_count")
    comments_count = _first_valid(interact, "commentCount", "comment_count")
    ip_location = note.get("ipLocation") or ""

    panel_text = Text()
    panel_text.append(f"作者: {nickname}", style="bold")
    if ip_location:
        panel_text.append(f"  📍{ip_location}")
    panel_text.append("\n")
    panel_text.append(f"👍 {likes}  ⭐ {collects}  💬 {comments_count}\n")
    panel_text.append(f"\n{content}\n")

    console.print(Panel(panel_text, title=f"📕 {title}", border_style="blue"))

    # 打印评论
    comments_data = parsed.get("data", {}).get("comments", {})
    comment_list = comments_data.get("list", [])
    if comment_list:
        table = Table(title=f"💬 评论 ({len(comment_list)} 条)", box=box.ROUNDED, show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("用户", max_width=14, overflow="fold")
        table.add_column("内容", max_width=45, overflow="fold")
        table.add_column("赞", justify="right", width=5)
        table.add_column("IP", width=6)

        for i, c in enumerate(comment_list, 1):
            c_user = c.get("userInfo", c.get("user", {}))
            table.add_row(
                str(i),
                c_user.get("nickname") or c_user.get("nickName") or "-",
                c.get("content", "-"),
                str(c.get("likeCount", "-")),
                c.get("ipLocation", "-"),
            )
        console.print(table)


def _unwrap_mcp_text(data: dict) -> dict:
    """从 MCP content[].text 中解包嵌套 JSON。"""
    if not isinstance(data, dict):
        return data
    content = data.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
    return data


def print_analytics(data: dict):
    """打印数据看板。"""
    rows = data.get("rows", [])
    if not rows:
        warning("暂无数据")
        return

    table = Table(title="📊 数据看板", box=box.ROUNDED, show_lines=True)
    table.add_column("标题", max_width=20, overflow="fold")
    table.add_column("发布时间", width=16)
    table.add_column("曝光", justify="right", width=8)
    table.add_column("观看", justify="right", width=8)
    table.add_column("点赞", justify="right", width=8)
    table.add_column("评论", justify="right", width=8)
    table.add_column("收藏", justify="right", width=8)
    table.add_column("涨粉", justify="right", width=8)

    for row in rows:
        table.add_row(
            str(row.get("标题", "-")),
            str(row.get("发布时间", "-")),
            str(row.get("曝光", "-")),
            str(row.get("观看", "-")),
            str(row.get("点赞", "-")),
            str(row.get("评论", "-")),
            str(row.get("收藏", "-")),
            str(row.get("涨粉", "-")),
        )

    console.print(table)


def print_profile(profile: dict):
    """打印用户资料（兼容 MCP 嵌套 JSON 格式）。"""
    # 解包 MCP content[].text
    user = _unwrap_mcp_text(profile)

    # 兼容驼峰 (MCP: userBasicInfo) 和蛇形 (basic_info)
    basic = (user.get("userBasicInfo")
             or user.get("basic_info")
             or user)
    nickname = basic.get("nickname") or basic.get("nickName") or "-"
    desc = basic.get("desc") or ""
    red_id = basic.get("redId") or basic.get("red_id") or "-"
    ip_loc = basic.get("ipLocation") or ""

    # interactions 可能是数组 [{"type":"fans","count":"9"}, ...] 或 dict
    interactions = user.get("interactions", [])
    fans = "-"
    follows = "-"
    liked = "-"
    if isinstance(interactions, list):
        for item in interactions:
            t = item.get("type", "")
            c = item.get("count", "-")
            if t == "fans":
                fans = c
            elif t == "follows":
                follows = c
            elif t == "interaction":
                liked = c
    elif isinstance(interactions, dict):
        fans = interactions.get("fans", "-")
        follows = interactions.get("follows", "-")
        liked = interactions.get("liked", "-")

    # fallback 到旧字段名
    if fans == "-":
        fans = str(basic.get("fans", user.get("fansCount", "-")))
    if follows == "-":
        follows = str(basic.get("follows", "-"))

    panel_text = Text()
    panel_text.append(f"昵称: {nickname}", style="bold")
    if ip_loc:
        panel_text.append(f"  📍{ip_loc}")
    panel_text.append("\n")
    panel_text.append(f"小红书号: {red_id}\n")
    panel_text.append(f"粉丝: {fans}  关注: {follows}  获赞与收藏: {liked}\n")
    if desc:
        panel_text.append(f"\n{desc}")

    console.print(Panel(panel_text, title="👤 用户资料", border_style="green"))

    # 如果有笔记列表也显示
    feeds = user.get("feeds", [])
    if feeds:
        print_feeds(feeds, keyword=f"{nickname} 的笔记")
