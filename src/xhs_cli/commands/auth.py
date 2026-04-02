"""
xhs login / logout / status — 认证命令。
"""

from __future__ import annotations

import os
import platform
import time
from typing import Any

import click

from xhs_cli.engines.cdp_client import CDPClient, CDPError
from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.output import console, error, info, status, success, warning


def _is_wsl() -> bool:
    """Detect WSL environment."""
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version") as f:
                content = f.read().lower()
                if "microsoft" in content or "wsl" in content:
                    return True
    except Exception:
        pass
    return "WSL_DISTRO_NAME" in os.environ or "wsl" in platform.release().lower()


def _is_macos() -> bool:
    """Detect macOS environment."""
    return platform.system() == "Darwin"


def _has_qrcode_content(result) -> bool:
    """Check if QR code result actually contains displayable content.

    MCP 有时返回 204 或空内容，此时二维码未真正生成。
    """
    if result is None:
        return False
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                # 有文本内容
                if item.get("type") == "text" and item.get("text", "").strip():
                    return True
                # 有图片内容
                if item.get("type") == "image" and item.get("url", "").strip():
                    return True
            return False
        # content 不是 list，检查是否有值
        return bool(content)
    # 非 dict，检查字符串是否非空
    return bool(str(result).strip())


@click.command("login", help="登录小红书 (MCP 扫码)")
@click.option("--account", default=None, help="账号名")
@click.option("--cdp", is_flag=True, help="使用 CDP 浏览器登录（打开 Chrome 扫码）")
def login(account, cdp):
    """登录小红书。"""
    if cdp:
        _login_cdp(account)
    else:
        _login_mcp(account=account)


def _ensure_mcp_server(cfg: dict[str, Any]) -> MCPClient:
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


def _login_mcp(account: str | None = None):
    """通过 MCP 获取二维码登录。如果 MCP 二维码获取失败，自动 fallback 到 CDP。"""
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

    # WSL/低配环境检测 — 调整超时和重试策略
    is_wsl = _is_wsl()
    max_retries = 3 if is_wsl else 2
    base_timeout = 600 if is_wsl else 300  # WSL 给 10 分钟

    if is_wsl:
        warning("WSL 环境检测，浏览器启动可能较慢，已自动延长超时时间")

    mcp_failed = False  # 记录 MCP 是否失败，用于决定是否 fallback

    for attempt in range(1, max_retries + 1):
        timeout = base_timeout + (attempt - 1) * 120  # 每次重试增加 2 分钟
        if attempt > 1:
            info(f"第 {attempt}/{max_retries} 次尝试（超时 {timeout}s）...")
            time.sleep(3)  # 重试前短暂等待
        else:
            info("正在获取登录二维码（浏览器启动可能较慢，请耐心等待）...")

        try:
            result = client.get_qrcode(timeout=timeout)

            # 校验二维码内容是否真正生成
            if not _has_qrcode_content(result):
                warning("服务端返回了空内容，二维码未成功生成")
                if attempt < max_retries:
                    warning(f"正在重试... ({attempt}/{max_retries})")
                    continue
                mcp_failed = True
                break

            # 二维码内容有效
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
            return  # 成功，退出
        except MCPError as e:
            err_msg = str(e)
            is_timeout = "timed out" in err_msg.lower() or "timeout" in err_msg.lower()

            if is_timeout and attempt < max_retries:
                warning(f"获取二维码超时，正在重试... ({attempt}/{max_retries})")
                continue  # 自动重试
            else:
                mcp_failed = True
                if is_timeout:
                    warning("获取二维码超时")
                else:
                    warning(f"获取二维码失败: {e}")
                break

    # --- MCP 失败，尝试自动 fallback 到 CDP ---
    if mcp_failed:
        _fallback_to_cdp(cfg, account, is_wsl)


def _fallback_to_cdp(cfg: dict[str, Any], account: str | None, is_wsl: bool):
    """MCP 二维码获取失败后，自动 fallback 到 CDP（系统 Chrome）登录。"""
    console.print()

    if is_wsl:
        # WSL 用户给出专门建议，不自动 fallback
        error("MCP 二维码获取失败")
        info("[bold yellow]WSL 用户建议:[/]")
        info("  1. 确保已安装 Chromium: [bold]sudo apt install chromium-browser[/]")
        info("  2. 或安装 Chrome: [bold]sudo apt install google-chrome-stable[/]")
        info("  3. 设置浏览器路径: [bold]export ROD_BROWSER_BIN=$(which chromium-browser)[/]")
        info("  4. 重启 MCP 服务后重试: [bold]xhs server restart && xhs login[/]")
        raise SystemExit(1)

    # macOS / Linux 桌面环境 — 自动尝试 CDP fallback
    warning("MCP 内置浏览器未能生成二维码，自动切换到系统 Chrome 登录...")
    console.print()

    try:
        cdp_client = CDPClient(
            host=cfg["cdp"]["host"],
            port=cfg["cdp"]["port"],
            account=account,
            headless=False,
        )
        output = cdp_client.login()
        if "LOGIN_READY" in output:
            success("登录页面已打开，请使用小红书 App 扫码")
            console.print()
            info("[bold]扫码成功后，运行 [green]xhs login[/green] 完成 MCP 登录[/]")
            info("[dim]（CDP 登录仅覆盖数据看板/通知，主要功能需 MCP 登录）[/]")
        else:
            console.print(output)
    except (CDPError, Exception) as e:
        error(f"CDP 登录也失败: {e}")
        console.print()
        info("请检查是否已安装 Google Chrome，或手动执行:")
        info("  [bold]xhs login --cdp[/]")
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
            console.print()
            info("[bold yellow]注意:[/] CDP 登录仅覆盖 [bold]数据看板、通知[/] 功能")
            info("搜索/发布/点赞/评论 等主要功能需要 MCP 登录:")
            info("  扫码完成后，还需运行: [bold]xhs login[/]")
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
                raise SystemExit(1)
            else:
                # engine == "all" 时不中断流程，但告知用户 MCP 退出失败
                warning(f"MCP 退出失败（已跳过）: {e}")

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
    mcp_logged_in = False
    mcp_running = MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
    if mcp_running:
        try:
            client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
            result = client.check_login()
            text = _extract_mcp_text(result)
            if "已登录" in text:
                mcp_logged_in = True
                status("MCP", "已登录  ← 搜索/发布/点赞/评论/收藏", "green")
            else:
                status("MCP", "未登录  ← 搜索/发布/点赞/评论/收藏", "yellow")
        except MCPError:
            status("MCP", "未登录  ← 搜索/发布/点赞/评论/收藏", "yellow")
    else:
        status("MCP", "服务未运行", "red")

    # CDP status
    cdp_logged_in = False
    try:
        cdp = CDPClient(
            host=cfg["cdp"]["host"],
            port=cfg["cdp"]["port"],
            headless=True,
            reuse_tab=True,
        )
        cdp_logged_in = cdp.check_login()
        status(
            "CDP",
            "已登录  ← 数据看板/通知" if cdp_logged_in else "未登录  ← 数据看板/通知",
            "green" if cdp_logged_in else "yellow",
        )
    except Exception:
        status("CDP", "Chrome 未启动  ← 数据看板/通知", "dim")

    # 给出操作建议
    console.print()
    if not mcp_running:
        info("启动服务: [bold]xhs server start[/]")
        info("  然后登录: [bold]xhs login[/]")
    elif not mcp_logged_in:
        if cdp_logged_in:
            info("[bold yellow]CDP 已登录，但主要功能需要 MCP 登录[/]")
        info("MCP 登录: [bold]xhs login[/]")

    console.print()
