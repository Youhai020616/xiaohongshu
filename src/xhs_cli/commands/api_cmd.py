"""
xhs api — REST API 服务管理命令。
"""
from __future__ import annotations

import click

from xhs_cli.utils.output import error, info, success


@click.group("api", help="REST API 服务管理")
def api_group():
    pass


@api_group.command("start", help="启动 REST API 服务")
@click.option("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
@click.option("--port", type=int, default=8080, help="监听端口 (默认 8080)")
@click.option("--reload", "auto_reload", is_flag=True, help="开发模式 (自动重载)")
def api_start(host, port, auto_reload):
    """启动 REST API 服务器。

    需要安装: pip install fastapi uvicorn
    """
    try:
        import uvicorn
    except ImportError:
        error("需要安装 uvicorn:")
        info("  pip install fastapi uvicorn")
        raise SystemExit(1)

    try:
        from xhs_cli.api.server import create_app  # noqa: F401
    except ImportError as e:
        error(f"API 模块加载失败: {e}")
        info("请安装依赖: pip install fastapi uvicorn")
        raise SystemExit(1)

    success(f"REST API 启动: http://{host}:{port}")
    info(f"API 文档: http://{host}:{port}/docs")
    info("按 Ctrl+C 停止")

    uvicorn.run(
        "xhs_cli.api.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=auto_reload,
    )
