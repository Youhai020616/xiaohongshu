"""
xhs init — 新用户引导式初始化。

自动完成: 检查环境 → 配置代理 → 启动 MCP → 登录。
"""
from __future__ import annotations

import os
import sys
import shutil
import platform

import click
from rich.panel import Panel
from rich.text import Text

from xhs_cli.engines.mcp_client import MCPClient, MCPError, MCP_BINARY
from xhs_cli.utils import config
from xhs_cli.utils.output import success, error, info, warning, console, status


@click.command("init", help="🚀 初始化设置 (新用户从这里开始)")
@click.option("--proxy", default=None, help="代理地址 (如 http://127.0.0.1:7897)")
@click.option("--no-proxy", is_flag=True, help="不使用代理 (在国内网络)")
@click.option("--port", type=int, default=18060, help="MCP 服务端口")
@click.option("--skip-login", is_flag=True, help="跳过登录步骤")
def init(proxy, no_proxy, port, skip_login):
    """引导新用户完成初始化。"""
    console.print()
    console.print(Panel(
        "[bold]欢迎使用 📕 xhs-cli — 小红书命令行工具[/]\n\n"
        "接下来将引导你完成初始化设置:\n"
        "  [dim]1.[/] 检查系统环境\n"
        "  [dim]2.[/] 配置网络代理\n"
        "  [dim]3.[/] 启动 MCP 服务\n"
        "  [dim]4.[/] 登录小红书账号",
        title="🚀 初始化向导",
        border_style="blue",
    ))
    console.print()

    # ── Step 1: 环境检查 ──────────────────────────────────
    console.rule("[bold]Step 1/4 — 环境检查[/]")
    console.print()

    # 系统
    arch = platform.machine()
    system = platform.system()
    status("系统", f"{system} {arch}")

    # MCP 二进制 — 检查是否存在且适用于当前平台
    mcp_available = os.path.isfile(MCP_BINARY) and (
        system == "Darwin" or not MCP_BINARY.endswith("-darwin-arm64")
    )
    if mcp_available:
        status("MCP 二进制", "✅ 已找到", "green")
    else:
        status("MCP 二进制", "⚠️ 未找到 (将使用 CDP 模式)", "yellow")
        if system != "Darwin" or arch != "arm64":
            info(f"当前平台 {system} {arch} 暂无 MCP 二进制")
        info("CDP 模式可用: 发布、搜索、数据看板等功能均支持")

    # Chrome (CDP 需要)
    chrome_ok = _check_chrome()
    if chrome_ok:
        status("Chrome", "✅ 已安装", "green")
    else:
        status("Chrome", "⚠️ 未找到 (CDP 功能不可用)", "yellow")

    # Python 依赖
    status("Python", f"{sys.version.split()[0]}")
    console.print()

    # ── Step 2: 代理配置 ─────────────────────────────────
    console.rule("[bold]Step 2/4 — 网络配置[/]")
    console.print()

    cfg = config.load_config()

    if no_proxy:
        proxy_addr = ""
        info("已选择不使用代理 (国内网络直连)")
    elif proxy:
        proxy_addr = proxy
        info(f"使用指定代理: {proxy}")
    else:
        # 交互式询问
        console.print("  小红书 API 在海外需要代理才能访问。")
        console.print("  如果你在[bold]国内[/]，可以直接回车跳过。")
        console.print()
        proxy_addr = click.prompt(
            "  代理地址",
            default=cfg["mcp"]["proxy"],
            show_default=True,
        )
        if proxy_addr.strip().lower() in ("none", "no", "skip", "跳过", "无", ""):
            proxy_addr = ""

    # 保存配置
    cfg["mcp"]["port"] = port
    cfg["mcp"]["proxy"] = proxy_addr
    config.save_config(cfg)
    success("配置已保存")
    console.print()

    # ── Step 3: 启动 MCP 服务 ─────────────────────────────
    console.rule("[bold]Step 3/4 — 启动 MCP 服务[/]")
    console.print()

    if not mcp_available:
        info("MCP 二进制不可用，跳过 MCP 服务启动")
        info("你可以使用 CDP 模式: [bold]xhs login --cdp[/]")
        cfg["default"]["engine"] = "cdp"
        config.save_config(cfg)
        skip_login = True
    elif MCPClient.is_running(port=port):
        pid = MCPClient.get_server_pid()
        success(f"MCP 服务已在运行 (PID: {pid})")
    else:
        info("正在启动 MCP 服务...")
        try:
            MCPClient.start_server(port=port, proxy=proxy_addr or None)
            pid = MCPClient.get_server_pid()
            success(f"MCP 服务已启动 (PID: {pid}, 端口: {port})")
        except MCPError as e:
            error(f"启动失败: {e}")
            warning("你可以稍后手动启动: xhs server start")
            if not skip_login:
                skip_login = True
    console.print()

    # ── Step 4: 登录 ─────────────────────────────────────
    console.rule("[bold]Step 4/4 — 登录小红书[/]")
    console.print()

    if skip_login:
        info("已跳过登录步骤")
        info("稍后使用 [bold]xhs login[/] 登录")
    else:
        # 检查是否已登录
        try:
            client = MCPClient(host="127.0.0.1", port=port)
            result = client.search("测试", {})
            success("已登录小红书 ✅")
        except MCPError:
            info("你尚未登录，正在获取登录二维码...")
            try:
                client = MCPClient(host="127.0.0.1", port=port)
                result = client.get_qrcode()
                console.print()
                console.print(Panel(
                    "[bold]请使用小红书 App 扫码登录:[/]\n\n"
                    "  1. 打开小红书 App\n"
                    "  2. 点击左上角 [bold]扫一扫[/]\n"
                    "  3. 扫描下方二维码\n\n"
                    "[dim]扫码后登录会自动完成，cookies 会持久保存。[/]",
                    title="📱 扫码登录",
                    border_style="green",
                ))

                # 显示二维码内容
                if isinstance(result, dict):
                    content = result.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text", "")
                                if text:
                                    console.print(text)
                else:
                    console.print(str(result))

            except MCPError as e:
                warning(f"获取二维码失败: {e}")
                info("稍后使用 [bold]xhs login[/] 重试")

    # ── 完成 ─────────────────────────────────────────────
    console.print()
    console.rule("[bold green]✅ 初始化完成[/]")
    console.print()
    # 根据平台显示不同提示
    if mcp_available:
        tips = (
            "[bold]🎉 你已准备就绪! 以下是常用命令:[/]\n\n"
            "  [bold cyan]xhs search[/] \"关键词\"          搜索笔记\n"
            "  [bold cyan]xhs publish[/] -t 标题 -c 正文 -i 图片  发布笔记\n"
            "  [bold cyan]xhs like[/] FEED_ID -t TOKEN    点赞\n"
            "  [bold cyan]xhs me[/]                       查看我的信息\n"
            "  [bold cyan]xhs analytics[/]                数据看板\n"
            "  [bold cyan]xhs server status[/]            服务状态\n"
            "  [bold cyan]xhs --help[/]                   查看所有命令\n\n"
            "[dim]提示: 大部分命令支持 --json-output 输出 JSON 格式[/]"
        )
    else:
        tips = (
            "[bold]🎉 你已准备就绪! (CDP 模式)[/]\n\n"
            "  [bold yellow]首先登录:[/]\n"
            "  [bold cyan]xhs login --cdp[/]              打开 Chrome 扫码登录\n\n"
            "  [bold yellow]然后使用:[/]\n"
            "  [bold cyan]xhs search[/] \"关键词\" --engine cdp   搜索笔记\n"
            "  [bold cyan]xhs publish[/] -t 标题 -c 正文 -i 图片 --engine cdp\n"
            "  [bold cyan]xhs analytics[/]                数据看板\n"
            "  [bold cyan]xhs notifications[/]            通知消息\n"
            "  [bold cyan]xhs --help[/]                   查看所有命令\n\n"
            "[dim]当前平台无 MCP 二进制，所有功能通过 CDP (Chrome) 实现[/]"
        )

    console.print(Panel(tips, title="📖 快速参考", border_style="cyan"))
    console.print()


def _check_chrome() -> bool:
    """检查 Chrome 是否已安装。"""
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif sys.platform == "win32":
        for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_var, "")
            if base:
                candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]

    for path in candidates:
        if os.path.isfile(path):
            return True

    return shutil.which("google-chrome") is not None or shutil.which("chromium") is not None
