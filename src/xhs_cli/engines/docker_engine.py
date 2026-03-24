"""
Docker Engine — 管理 Docker 容器化的 MCP 服务。

通过 docker compose 管理上游 xpzouying/xiaohongshu-mcp 镜像的生命周期。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DOCKER_DIR = os.path.join(_PROJECT_ROOT, "docker")
COMPOSE_FILE = os.path.join(DOCKER_DIR, "docker-compose.yml")
CONTAINER_NAME = "xhs-mcp"


class DockerError(Exception):
    """Docker 操作错误。"""


def is_docker_available() -> bool:
    """检查 docker 和 docker compose 是否可用。"""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_container_running() -> bool:
    """检查 MCP 容器是否正在运行。"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def get_container_status() -> dict[str, Any]:
    """获取容器详细状态。"""
    info: dict[str, Any] = {
        "running": False,
        "container_name": CONTAINER_NAME,
        "image": "",
        "status": "not found",
        "ports": "",
    }
    try:
        fmt = "{{.State.Status}}|{{.Config.Image}}|{{.State.StartedAt}}"
        result = subprocess.run(
            ["docker", "inspect", "-f", fmt, CONTAINER_NAME],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            info["status"] = parts[0] if len(parts) > 0 else "unknown"
            info["image"] = parts[1] if len(parts) > 1 else ""
            info["started_at"] = parts[2] if len(parts) > 2 else ""
            info["running"] = info["status"] == "running"

        # 获取端口映射
        port_result = subprocess.run(
            ["docker", "port", CONTAINER_NAME],
            capture_output=True, text=True, timeout=5,
        )
        if port_result.returncode == 0:
            info["ports"] = port_result.stdout.strip()
    except Exception:
        pass
    return info


def start(port: int = 18060, proxy: str | None = None) -> None:
    """启动 Docker MCP 服务。"""
    if not is_docker_available():
        raise DockerError(
            "Docker 不可用。请先安装 Docker Desktop:\n"
            "  macOS/Windows: https://www.docker.com/products/docker-desktop\n"
            "  Linux: https://docs.docker.com/engine/install/"
        )

    if not os.path.isfile(COMPOSE_FILE):
        raise DockerError(f"docker-compose.yml 不存在: {COMPOSE_FILE}")

    if is_container_running():
        raise DockerError("Docker MCP 服务已在运行")

    # 创建数据目录
    os.makedirs(os.path.join(DOCKER_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(DOCKER_DIR, "images"), exist_ok=True)

    # 构建环境变量
    env = {**os.environ, "MCP_PORT": str(port)}
    if proxy:
        env["XHS_PROXY"] = proxy

    # 启动
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"],
        capture_output=True, text=True, env=env, cwd=DOCKER_DIR,
    )
    if result.returncode != 0:
        raise DockerError(f"Docker 启动失败:\n{result.stderr}")


def stop() -> None:
    """停止 Docker MCP 服务。"""
    if not is_container_running():
        return

    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop"],
        capture_output=True, text=True, cwd=DOCKER_DIR,
    )
    if result.returncode != 0:
        raise DockerError(f"Docker 停止失败:\n{result.stderr}")


def remove() -> None:
    """停止并删除 Docker MCP 容器。"""
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "down"],
        capture_output=True, text=True, cwd=DOCKER_DIR,
    )
    if result.returncode != 0:
        raise DockerError(f"Docker 清理失败:\n{result.stderr}")


def logs(lines: int = 50, follow: bool = False) -> str:
    """获取容器日志。"""
    cmd = ["docker", "logs", "--tail", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(CONTAINER_NAME)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.stdout + result.stderr


def pull() -> None:
    """拉取最新镜像。"""
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "pull"],
        capture_output=True, text=True, cwd=DOCKER_DIR,
    )
    if result.returncode != 0:
        raise DockerError(f"拉取镜像失败:\n{result.stderr}")
