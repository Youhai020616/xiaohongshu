"""
xhs server — MCP 服务管理命令。

支持三种后端: 本地二进制 / Docker / 远程连接。
"""

from __future__ import annotations

import os

import click

from xhs_cli.engines import docker_engine
from xhs_cli.engines.mcp_binary import (
    build_from_source,
    detect_platform,
    download_binary,
    ensure_binary,
    get_installed_version,
    is_binary_available,
    is_go_available,
    is_source_available,
)
from xhs_cli.engines.mcp_client import MCP_BINARY, MCP_LOG_FILE, MCPClient, MCPError
from xhs_cli.utils import config
from xhs_cli.utils.output import console, error, info, status, success, warning


@click.group("server", help="MCP 服务管理")
def server_group():
    pass


# ══════════════════════════════════════════════════════
#  install — 安装二进制
# ══════════════════════════════════════════════════════


@server_group.command("install", help="安装当前平台的 MCP 二进制")
@click.option("--from-source", is_flag=True, help="从源码编译 (需要 Go 环境)")
@click.option("--force", is_flag=True, help="强制重新安装")
def install(from_source, force):
    """下载或编译当前平台的 MCP 二进制。"""
    os_name, arch_name = detect_platform()
    info(f"当前平台: {os_name}-{arch_name}")

    if is_binary_available() and not force:
        ver = get_installed_version()
        tag = ver["tag"] if ver else "unknown"
        success(f"MCP 二进制已安装 (版本: {tag})")
        info("使用 --force 强制重新安装")
        return

    if from_source:
        if not is_go_available():
            error("未检测到 Go 编译器")
            info("安装 Go: https://go.dev/doc/install")
            raise SystemExit(1)
        if not is_source_available():
            error("源码目录不存在: sources/xiaohongshu-mcp")
            info("请先克隆源码: git clone https://github.com/xpzouying/xiaohongshu-mcp.git sources/xiaohongshu-mcp")
            raise SystemExit(1)

        info("正在从源码编译...")
        try:
            tag = build_from_source()
            success(f"编译完成 (版本: {tag})")
        except RuntimeError as e:
            error(str(e))
            raise SystemExit(1)
    else:
        info("正在从 GitHub Releases 下载...")
        try:
            from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("下载中...", total=None)

                def on_progress(downloaded, total):
                    if total and progress.tasks[task].total != total:
                        progress.update(task, total=total)
                    progress.update(task, completed=downloaded)

                tag = download_binary(progress_callback=on_progress)

            success(f"下载完成 (版本: {tag})")
        except RuntimeError as e:
            error(str(e))
            raise SystemExit(1)

    status("二进制", MCP_BINARY)


# ══════════════════════════════════════════════════════
#  start — 启动服务 (二进制 / Docker)
# ══════════════════════════════════════════════════════


@server_group.command("start", help="启动 MCP 服务")
@click.option("--port", type=int, default=None, help="端口号 (默认: 18060)")
@click.option("--proxy", default=None, help="代理地址")
@click.option("--no-proxy", is_flag=True, help="不使用代理")
@click.option("--docker", is_flag=True, help="使用 Docker 容器运行 (无需安装 Go/二进制)")
@click.option("--auto-install/--no-auto-install", default=True, help="二进制不存在时自动安装 (默认开启)")
def start(port, proxy, no_proxy, docker, auto_install):
    """启动 MCP 服务。"""
    cfg = config.load_config()
    port = port or cfg["mcp"]["port"]
    proxy_addr = None if no_proxy else (proxy or cfg["mcp"].get("proxy"))

    # ── Docker 模式 ──
    if docker:
        _start_docker(port, proxy_addr)
        return

    # ── 二进制模式 ──
    # 先检查 MCP 是否已通过任何方式运行 (二进制或 Docker)
    if MCPClient.is_running(port=port):
        pid = MCPClient.get_server_pid()
        if pid:
            success(f"MCP 服务已在运行 (PID: {pid}, 端口: {port})")
        elif docker_engine.is_container_running():
            success(f"MCP 服务已在运行 (Docker 容器: {docker_engine.CONTAINER_NAME})")
        else:
            success(f"MCP 服务已在运行 (端口: {port})")
        return

    # 二进制不存在时自动安装
    if not os.path.isfile(MCP_BINARY):
        if auto_install:
            os_name, arch_name = detect_platform()
            info(f"MCP 二进制不存在，正在自动安装 ({os_name}-{arch_name})...")
            try:
                tag = ensure_binary()
                success(f"安装完成 (版本: {tag})")
            except RuntimeError as e:
                error(str(e))
                info("或者使用 Docker 模式: [bold]xhs server start --docker[/]")
                info("或者使用 CDP 模式: [bold]xhs login --cdp[/]")
                raise SystemExit(1)
        else:
            error(f"MCP 二进制不可用: {os.path.basename(MCP_BINARY)}")
            info("运行 [bold]xhs server install[/] 安装")
            info("或者使用 Docker: [bold]xhs server start --docker[/]")
            raise SystemExit(1)

    info(f"正在启动 MCP 服务 (端口: {port})...")
    if proxy_addr:
        info(f"代理: {proxy_addr}")

    try:
        MCPClient.start_server(port=port, proxy=proxy_addr or "")
        pid = MCPClient.get_server_pid()
        success(f"MCP 服务已启动 (PID: {pid})")
        status("端口", str(port))
        status("日志", MCP_LOG_FILE)
    except MCPError as e:
        error(str(e))
        raise SystemExit(1)


def _start_docker(port: int, proxy: str | None):
    """Docker 模式启动。"""
    if not docker_engine.is_docker_available():
        error("Docker 不可用")
        info("请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop")
        info("或使用二进制模式: [bold]xhs server start[/]")
        raise SystemExit(1)

    if docker_engine.is_container_running():
        success(f"Docker MCP 服务已在运行 (容器: {docker_engine.CONTAINER_NAME})")
        return

    info("正在启动 Docker MCP 服务...")
    if proxy:
        info(f"代理: {proxy}")

    try:
        docker_engine.start(port=port, proxy=proxy)
        # 等待服务就绪
        import time

        ready = False
        for i in range(20):
            time.sleep(1)
            if MCPClient.is_running(port=port):
                ready = True
                break

        if ready:
            success("Docker MCP 服务已启动")
            status("容器", docker_engine.CONTAINER_NAME)
            status("端口", str(port))
            status("地址", f"http://127.0.0.1:{port}/mcp")
            info("本地图片请放入 [bold]docker/images/[/] 目录")
            info("容器内路径: [bold]/app/images/[/]")
        else:
            warning("Docker 容器已启动但 MCP 服务未就绪")
            info("可能仍在初始化，请稍后运行 [bold]xhs server status --docker[/] 检查")
            info(f"或查看日志: docker logs {docker_engine.CONTAINER_NAME}")
    except docker_engine.DockerError as e:
        error(str(e))
        raise SystemExit(1)


# ══════════════════════════════════════════════════════
#  stop — 停止服务
# ══════════════════════════════════════════════════════


@server_group.command("stop", help="停止 MCP 服务")
@click.option("--docker", is_flag=True, help="停止 Docker 容器")
def stop(docker):
    """停止 MCP 服务。"""
    if docker:
        _stop_docker()
        return

    # 尝试停止本地进程
    pid = MCPClient.get_server_pid()
    if pid:
        if MCPClient.stop_server():
            success(f"MCP 服务已停止 (PID: {pid})")
        else:
            error("停止 MCP 服务失败")
            raise SystemExit(1)
        return

    # 没有本地进程，检查 Docker
    if docker_engine.is_container_running():
        info("检测到 Docker 容器运行中，正在停止...")
        _stop_docker()
        return

    info("MCP 服务未在运行")


def _stop_docker():
    """停止 Docker 容器。"""
    if not docker_engine.is_container_running():
        info("Docker MCP 服务未在运行")
        return
    try:
        docker_engine.stop()
        success(f"Docker MCP 服务已停止 (容器: {docker_engine.CONTAINER_NAME})")
    except docker_engine.DockerError as e:
        error(str(e))
        raise SystemExit(1)


# ══════════════════════════════════════════════════════
#  status — 查看状态
# ══════════════════════════════════════════════════════


@server_group.command("status", help="查看 MCP 服务状态")
@click.option("--port", type=int, default=None, help="端口号")
def server_status(port):
    """查看 MCP 服务状态。"""
    cfg = config.load_config()
    port = port or cfg["mcp"]["port"]

    console.print()

    # HTTP 连通性
    http_ok = MCPClient.is_running(port=port)

    # 本地进程
    pid = MCPClient.get_server_pid()

    # Docker 容器
    docker_running = docker_engine.is_container_running()

    if http_ok:
        success("MCP 服务运行中")
        status("地址", f"http://127.0.0.1:{port}/mcp")
        if pid:
            status("模式", "本地二进制")
            status("PID", str(pid))
        elif docker_running:
            docker_info = docker_engine.get_container_status()
            status("模式", "Docker 容器")
            status("容器", docker_engine.CONTAINER_NAME)
            status("镜像", docker_info.get("image", "unknown"))
        else:
            status("模式", "外部服务")
        status("端口", str(port))
    else:
        error("MCP 服务未运行")
        if docker_running:
            warning("Docker 容器在运行但 HTTP 未就绪 (可能正在初始化)")
        console.print()
        info("启动方式:")
        info("  [bold]xhs server start[/]          本地二进制")
        info("  [bold]xhs server start --docker[/]  Docker 容器")

    console.print()


# ══════════════════════════════════════════════════════
#  log — 查看日志
# ══════════════════════════════════════════════════════


@server_group.command("log", help="查看 MCP 服务日志")
@click.option("-n", "--lines", type=int, default=50, help="显示最后 N 行")
@click.option("--docker", is_flag=True, help="查看 Docker 容器日志")
def log(lines, docker):
    """查看 MCP 日志。"""
    if docker:
        if not docker_engine.is_container_running():
            info("Docker MCP 服务未在运行")
            return
        output = docker_engine.logs(lines=lines)
        console.print(output)
        return

    if not os.path.exists(MCP_LOG_FILE):
        # 自动检测: 如果本地日志不存在但 Docker 在运行
        if docker_engine.is_container_running():
            info("本地日志不存在，显示 Docker 容器日志:")
            output = docker_engine.logs(lines=lines)
            console.print(output)
            return
        info("日志文件不存在")
        return

    with open(MCP_LOG_FILE) as f:
        all_lines = f.readlines()
    for line in all_lines[-lines:]:
        console.print(line.rstrip())
