"""
xhs publish — 发布命令（自动选择最优引擎）。
"""

from __future__ import annotations

import os

import click

from xhs_cli.engines.cdp_client import CDPClient, CDPError
from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.output import console, error, info, success, warning


@click.command("publish", help="发布笔记到小红书")
@click.option("--title", "-t", required=True, help="标题 (≤20字)")
@click.option("--content", "-c", default=None, help="正文 (≤1000字)")
@click.option("--content-file", type=click.Path(exists=True), default=None, help="从文件读取正文")
@click.option("--images", "-i", multiple=True, help="图片路径或 URL (可多个)")
@click.option("--video", "-v", default=None, help="视频文件路径")
@click.option("--tags", multiple=True, help="标签 (可多个，如: --tags 旅行 --tags 美食)")
@click.option(
    "--visibility", type=click.Choice(["公开可见", "仅自己可见", "仅互关好友可见"]), default="公开可见", help="可见范围"
)
@click.option("--original", is_flag=True, help="声明原创")
@click.option("--schedule", default=None, help="定时发布 (ISO 8601, 如 2026-03-15T10:30:00+08:00)")
@click.option("--products", multiple=True, help="商品关键词 (可多个，如: --products 面膜 --products 防晒霜)")
@click.option("--engine", type=click.Choice(["auto", "mcp", "cdp"]), default="auto", help="指定引擎 (默认自动选择)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--dry-run", is_flag=True, help="预览模式，不实际发布")
def publish(
    title,
    content,
    content_file,
    images,
    video,
    tags,
    visibility,
    original,
    schedule,
    products,
    engine,
    account,
    dry_run,
):
    """发布图文或视频笔记。"""

    # 处理正文
    if content_file:
        with open(content_file, encoding="utf-8") as f:
            content = f.read().strip()
    if not content:
        error("正文不能为空，请使用 --content 或 --content-file")
        raise SystemExit(1)

    # 处理媒体
    images = list(images)
    if not images and not video:
        error("必须提供图片 (--images) 或视频 (--video)")
        raise SystemExit(1)

    if video and images:
        error("不能同时提供图片和视频，请选择一种")
        raise SystemExit(1)

    # 验证文件存在
    if video and not video.startswith("http") and not os.path.isfile(video):
        error(f"视频文件不存在: {video}")
        raise SystemExit(1)

    for img in images:
        if not img.startswith("http") and not os.path.isfile(img):
            error(f"图片文件不存在: {img}")
            raise SystemExit(1)

    tags = list(tags)
    products = list(products)

    # 预览模式
    if dry_run:
        console.print()
        info("📋 发布预览:")
        console.print(f"  [bold]标题:[/] {title}")
        console.print(f"  [bold]正文:[/] {content[:100]}{'...' if len(content) > 100 else ''}")
        if video:
            console.print(f"  [bold]视频:[/] {video}")
        else:
            console.print(f"  [bold]图片:[/] {', '.join(images)}")
        if tags:
            console.print(f"  [bold]标签:[/] {', '.join(tags)}")
        if products:
            console.print(f"  [bold]商品:[/] {', '.join(products)}")
        console.print(f"  [bold]可见:[/] {visibility}")
        if schedule:
            console.print(f"  [bold]定时:[/] {schedule}")
        console.print()
        return

    # 选择引擎
    cfg = config.load_config()
    if engine == "auto":
        engine = cfg["default"].get("engine", "auto")

    if engine == "auto":
        # MCP 优先：常驻，更快
        if MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"]):
            engine = "mcp"
        else:
            engine = "cdp"
            warning("MCP 服务未运行，使用 CDP 引擎发布")

    # 执行发布
    if engine == "mcp":
        _publish_mcp(cfg, title, content, images, video, tags, visibility, original, schedule, products)
    else:
        if products:
            warning("--products 仅 MCP 引擎支持，CDP 引擎将忽略")
        if visibility and visibility != "公开可见":
            warning(f"--visibility '{visibility}' 仅 MCP 引擎支持，CDP 引擎将以默认可见范围发布")
        if schedule:
            warning("--schedule 仅 MCP 引擎支持，CDP 引擎将立即发布")
        if original:
            warning("--original 仅 MCP 引擎支持，CDP 引擎将忽略")
        _publish_cdp(cfg, title, content, images, video, tags, account)


def _publish_mcp(cfg, title, content, images, video, tags, visibility, original, schedule, products):
    """通过 MCP 发布。"""
    client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])

    info("正在通过 MCP 发布...")
    try:
        if video:
            client.publish_video(
                title=title,
                content=content,
                video=os.path.abspath(video),
                tags=tags or None,
                visibility=visibility,
                schedule_at=schedule,
                products=products or None,
            )
        else:
            client.publish(
                title=title,
                content=content,
                images=images,
                tags=tags or None,
                visibility=visibility,
                is_original=original,
                schedule_at=schedule,
                products=products or None,
            )

        success("发布成功! 🎉")
        info("提示: PostID 返回空是正常行为，可用 [bold]xhs search[/] 搜索验证")

    except MCPError as e:
        error(f"MCP 发布失败: {e}")
        warning("发布超时不代表失败，请先用 xhs search 验证后再重试")
        raise SystemExit(1)


def _publish_cdp(cfg, title, content, images, video, tags, account):
    """通过 CDP 发布。"""
    client = CDPClient(
        host=cfg["cdp"]["host"],
        port=cfg["cdp"]["port"],
        account=account,
        headless=cfg["cdp"].get("headless", False),
        reuse_tab=True,
    )

    # 判断是 URL 还是本地文件
    image_urls = [img for img in images if img.startswith("http")]
    local_images = [img for img in images if not img.startswith("http")]

    info("正在通过 CDP 发布...")
    try:
        output = client.publish(
            title=title,
            content=content,
            images=local_images or None,
            image_urls=image_urls or None,
            video=video,
            auto_publish=True,
        )
        if "PUBLISHED" in output:
            success("发布成功! 🎉")
        elif "READY_TO_PUBLISH" in output:
            success("内容已填写，请在浏览器中确认发布")
        elif "NOT_LOGGED_IN" in output:
            error("未登录，请先运行: xhs login --cdp")
            raise SystemExit(1)
        else:
            console.print(output)
    except CDPError as e:
        error(f"CDP 发布失败: {e}")
        raise SystemExit(1)
