"""
xhs login / logout / status — 认证命令。
"""
from __future__ import annotations

import click

from xhs_cli.engines.cdp_client import CDPClient, CDPError
from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.output import console, error, info, status, success


@click.command("login", help="登录小红书 (MCP 扫码)")
@click.option("--account", default=None, help="账号名")
@click.option("--cdp", is_flag=True, help="使用 CDP 浏览器登录（打开 Chrome 扫码）")
def login(account, cdp):
    """登录小红书。"""
    if cdp:
        _login_cdp(account)
    else:
        _login_mcp()


def _ensure_mcp_server(cfg: dict) -> MCPClient:
    """确保 MCP 服务运行中，返回可用的 client。"""
    host = cfg["mcp"]["host"]
    port = cfg["mcp"]["port"]
    auto_start = cfg["mcp"].get("auto_start", True)

    if MCPClient.is_running(host=host, port=port):
        return MCPClient(host=host, port=port)

    if not auto_start:
        error("MCP 服务未运行")
        info("请先启动: [bold]xhs server start[/]")
        raise SystemExit(1)

    # 自动启动 MCP 服务
    info("正在自动启动 MCP 服务...")
    try:
        proxy = cfg["mcp"].get("proxy", "")
        MCPClient.start_server(port=port, proxy=proxy)
        success("MCP 服务已启动")
        return MCPClient(host=host, port=port)
    except MCPError as e:
        error(f"MCP 服务启动失败: {e}")
        info("请手动启动: [bold]xhs server start[/]")
        info("或使用 Docker: [bold]xhs server start --docker[/]")
        raise SystemExit(1)


def _login_mcp():
    """通过 MCP 获取二维码登录。"""
    cfg = config.load_config()

    # 确保 MCP 服务运行中（自动启动）
    client = _ensure_mcp_server(cfg)

    # 先检查是否已登录
    info("正在检查登录状态...")
    try:
        result = client.check_login()
        text = _extract_mcp_text(result)
        if "已登录" in text:
            success("已登录小红书")
            return
    except MCPError:
        pass

    info("正在获取登录二维码（浏览器启动可能较慢，请耐心等待）...")
    try:
        result = client.get_qrcode(timeout=300)
        console.print()
        success("二维码已生成，请使用小红书 App 扫码登录")
        info("打开小红书 App → 左上角扫一扫 → 扫描二维码")
        console.print()

        # 显示二维码数据（如果有 base64 图片数据）
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        console.print(item.get("text", ""))
                    elif isinstance(item, dict) and item.get("type") == "image":
                        info("二维码图片已生成（在支持的终端中查看）")
                        url = item.get("url", "")
                        if url:
                            console.print(f"  [dim]{url[:80]}...[/]")
        else:
            console.print(str(result))
    except MCPError as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            error("获取二维码超时")
            info("可能原因: 浏览器启动较慢（WSL/低配机器常见）")
            info("如果二维码已弹出，请先扫码登录，然后运行: [bold]xhs status[/] 检查")
            info("否则请重试: [bold]xhs login[/]")
        else:
            error(f"获取二维码失败: {e}")
            info("请检查 MCP 服务状态: [bold]xhs server status[/]")
        raise SystemExit(1)


def _extract_mcp_text(result) -> str:
    """从 MCP 结果中提取文本。"""
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts)
        return result.get("text", str(result))
    return str(result)


def _login_cdp(account):
    """通过 CDP 浏览器登录。"""
    cfg = config.load_config()
    client = CDPClient(
        host=cfg["cdp"]["host"],
        port=cfg["cdp"]["port"],
        account=account,
        headless=False,  # login 必须有头
    )

    # cdp_publish.py login 内部会自动启动/重启 Chrome，无需先调 start_chrome()
    info("正在启动 Chrome 并打开登录页面...")
    try:
        output = client.login()
        if "LOGIN_READY" in output:
            success("登录页面已打开，请使用小红书 App 扫码")
            info("扫码完成后，运行 [bold]xhs status[/] 确认登录状态")
        else:
            console.print(output)
    except CDPError as e:
        err_msg = str(e)
        if "Chrome" in err_msg or "chrome" in err_msg or "not found" in err_msg.lower():
            error("Chrome 浏览器启动失败")
            info("请确保已安装 Google Chrome:")
            info("  Linux: [bold]sudo apt install google-chrome-stable[/]")
            info("  或使用 MCP 登录: [bold]xhs login[/]")
        else:
            error(f"CDP 登录失败: {e}")
        raise SystemExit(1)


@click.command("logout", help="退出登录")
@click.option("--engine", type=click.Choice(["mcp", "cdp", "all"]), default="all", help="指定引擎")
def logout(engine):
    """退出登录（删除 cookies）。"""
    cfg = config.load_config()

    if engine in ("mcp", "all"):
        try:
            client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
            client.delete_cookies()
            success("MCP 登录态已清除")
        except MCPError as e:
            if engine == "mcp":
                error(f"MCP 退出失败: {e}")

    if engine in ("cdp", "all"):
        info("CDP 登录态需要手动清除（运行 xhs login --cdp 重新登录）")


@click.command("reset-login", help="重置登录状态 (删除 MCP Cookies)")
@click.confirmation_option(prompt="确定要重置登录状态吗？重置后需要重新扫码登录")
def reset_login():
    """删除 MCP Cookies 文件，重置登录状态。比 logout 更彻底。"""
    cfg = config.load_config()

    if not MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"]):
        error("MCP 服务未运行，请先启动: xhs server start")
        raise SystemExit(1)

    info("正在重置登录状态...")
    try:
        client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
        result = client.delete_cookies()
        success("登录状态已重置 ✅")
        info("请运行 [bold]xhs login[/] 重新扫码登录")

        # 显示服务端返回的详细信息
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        if text:
                            info(f"服务端: {text}")
    except MCPError as e:
        error(f"重置失败: {e}")
        raise SystemExit(1)


@click.command("status", help="查看登录状态")
def auth_status():
    """查看各引擎的登录状态。"""
    cfg = config.load_config()
    console.print()

    # MCP status
    mcp_running = MCPClient.is_running(
        host=cfg["mcp"]["host"], port=cfg["mcp"]["port"]
    )
    if mcp_running:
        try:
            client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
            result = client.check_login()
            text = _extract_mcp_text(result)
            if "已登录" in text:
                status("MCP", "已登录", "green")
            else:
                status("MCP", "未登录", "yellow")
        except MCPError:
            status("MCP", "未登录", "yellow")
    else:
        status("MCP", "服务未运行", "red")

    # CDP status
    try:
        cdp = CDPClient(
            host=cfg["cdp"]["host"],
            port=cfg["cdp"]["port"],
            headless=True,
            reuse_tab=True,
        )
        logged_in = cdp.check_login()
        status("CDP", "已登录" if logged_in else "未登录", "green" if logged_in else "yellow")
    except Exception:
        status("CDP", "Chrome 未启动", "dim")

    console.print()
