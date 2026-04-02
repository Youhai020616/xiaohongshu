"""
MCP 二进制管理 — 下载 / 编译 / 版本管理。

支持从 GitHub Releases 自动下载当前平台的预编译二进制，
或从本地源码编译（需要 Go 环境）。
"""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from typing import Any

import requests

# ── 常量 ──────────────────────────────────────────────────
GITHUB_REPO = "xpzouying/xiaohongshu-mcp"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MCP_DIR = os.path.join(_PROJECT_ROOT, "mcp")
SOURCE_DIR = os.path.join(_PROJECT_ROOT, "sources", "xiaohongshu-mcp")
VERSION_FILE = os.path.join(MCP_DIR, ".version.json")


# ── 平台检测 ──────────────────────────────────────────────


def detect_platform() -> tuple[str, str]:
    """检测当前平台，返回 (os_name, arch_name)。"""
    system = platform.system().lower()
    arch = platform.machine().lower()

    os_map = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
    os_name = os_map.get(system, system)

    if arch in ("arm64", "aarch64"):
        arch_name = "arm64"
    elif arch in ("x86_64", "amd64", "x64"):
        arch_name = "amd64"
    else:
        arch_name = arch

    return os_name, arch_name


def get_binary_names(os_name: str, arch_name: str) -> tuple[str, str]:
    """返回 (mcp_binary_name, login_binary_name)。"""
    ext = ".exe" if os_name == "windows" else ""
    return (
        f"xiaohongshu-mcp-{os_name}-{arch_name}{ext}",
        f"xiaohongshu-login-{os_name}-{arch_name}{ext}",
    )


def get_binary_path() -> str:
    """获取当前平台 MCP 二进制的完整路径。"""
    os_name, arch_name = detect_platform()
    mcp_name, _ = get_binary_names(os_name, arch_name)
    return os.path.join(MCP_DIR, mcp_name)


def get_login_binary_path() -> str:
    """获取当前平台登录二进制的完整路径。"""
    os_name, arch_name = detect_platform()
    _, login_name = get_binary_names(os_name, arch_name)
    return os.path.join(MCP_DIR, login_name)


def is_binary_available() -> bool:
    """检查当前平台二进制是否存在。"""
    return os.path.isfile(get_binary_path())


# ── 版本管理 ──────────────────────────────────────────────


def get_installed_version() -> dict[str, Any] | None:
    """获取已安装的版本信息。"""
    if not os.path.exists(VERSION_FILE):
        return None
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_version(tag: str, method: str):
    """保存版本信息。"""
    os.makedirs(MCP_DIR, exist_ok=True)
    # 只调用一次 detect_platform()，避免重复计算
    os_name, arch = detect_platform()
    info = {
        "tag": tag,
        "method": method,  # "download" | "build"
        "platform": f"{os_name}-{arch}",
    }
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


# ── GitHub Releases 下载 ──────────────────────────────────


def fetch_latest_release() -> dict[str, Any]:
    """获取最新 Release 信息。"""
    resp = requests.get(GITHUB_API, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _find_asset(release: dict, os_name: str, arch_name: str) -> dict | None:
    """在 Release 中查找匹配当前平台的资源。"""
    # 命名规则: xiaohongshu-mcp-{os}-{arch}.tar.gz 或 .zip
    suffix = ".zip" if os_name == "windows" else ".tar.gz"
    target = f"xiaohongshu-mcp-{os_name}-{arch_name}{suffix}"

    for asset in release.get("assets", []):
        if asset["name"] == target:
            return asset
    return None


def download_binary(progress_callback=None) -> str:
    """
    从 GitHub Releases 下载当前平台的 MCP 二进制。

    Args:
        progress_callback: 可选回调 fn(downloaded_bytes, total_bytes)

    Returns:
        安装后的版本 tag

    Raises:
        RuntimeError: 下载失败
    """
    os_name, arch_name = detect_platform()
    release = fetch_latest_release()
    tag = release.get("tag_name", "unknown")

    asset = _find_asset(release, os_name, arch_name)
    if not asset:
        supported = [a["name"] for a in release.get("assets", [])]
        raise RuntimeError(
            f"当前平台 {os_name}-{arch_name} 无预编译二进制。\n"
            f"可用: {', '.join(supported)}\n"
            f"可尝试源码编译: xhs server install --from-source"
        )

    download_url = asset["browser_download_url"]
    total_size = asset.get("size", 0)

    # 下载
    resp = requests.get(download_url, stream=True, timeout=60)
    resp.raise_for_status()

    buf = io.BytesIO()
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=8192):
        buf.write(chunk)
        downloaded += len(chunk)
        if progress_callback:
            progress_callback(downloaded, total_size)

    buf.seek(0)

    # 解压（校验路径防止 path traversal 攻击）
    os.makedirs(MCP_DIR, exist_ok=True)
    abs_mcp_dir = os.path.realpath(MCP_DIR)

    if asset["name"].endswith(".zip"):
        with zipfile.ZipFile(buf) as zf:
            for member in zf.namelist():
                dest = os.path.realpath(os.path.join(MCP_DIR, member))
                if not dest.startswith(abs_mcp_dir + os.sep) and dest != abs_mcp_dir:
                    raise RuntimeError(f"压缩包路径不安全，拒绝解压: {member}")
            zf.extractall(MCP_DIR)
    else:
        with tarfile.open(fileobj=buf, mode="r:gz") as tf:
            for member in tf.getmembers():
                dest = os.path.realpath(os.path.join(MCP_DIR, member.name))
                if not dest.startswith(abs_mcp_dir + os.sep) and dest != abs_mcp_dir:
                    raise RuntimeError(f"压缩包路径不安全，拒绝解压: {member.name}")
            # Python 3.12+ extractall 要求显式指定 filter 参数，否则产生弃用警告
            if sys.version_info >= (3, 12):
                tf.extractall(MCP_DIR, filter="data")
            else:
                tf.extractall(MCP_DIR)

    # 设置可执行权限 (非 Windows)
    if os_name != "windows":
        mcp_name, login_name = get_binary_names(os_name, arch_name)
        for name in (mcp_name, login_name):
            path = os.path.join(MCP_DIR, name)
            if os.path.isfile(path):
                os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    _save_version(tag, "download")
    return tag


# ── 源码编译 ──────────────────────────────────────────────


def is_go_available() -> bool:
    """检查 Go 编译器是否可用。"""
    return shutil.which("go") is not None


def is_source_available() -> bool:
    """检查源码是否存在。"""
    return os.path.isfile(os.path.join(SOURCE_DIR, "go.mod"))


def build_from_source(source_dir: str | None = None) -> str:
    """
    从源码编译当前平台的 MCP 二进制。

    Args:
        source_dir: 源码目录，默认 sources/xiaohongshu-mcp

    Returns:
        版本标识

    Raises:
        RuntimeError: 编译失败
    """
    src = source_dir or SOURCE_DIR

    if not os.path.isfile(os.path.join(src, "go.mod")):
        raise RuntimeError(f"源码目录不存在或无效: {src}")

    if not is_go_available():
        raise RuntimeError("未检测到 Go 编译器，请先安装: https://go.dev/doc/install")

    os_name, arch_name = detect_platform()
    mcp_name, login_name = get_binary_names(os_name, arch_name)
    os.makedirs(MCP_DIR, exist_ok=True)

    # Go 环境变量
    env = {
        **os.environ,
        "GOOS": os_name,
        "GOARCH": arch_name,
        "CGO_ENABLED": "0",
    }

    # 编译主程序
    mcp_output = os.path.join(MCP_DIR, mcp_name)
    result = subprocess.run(
        ["go", "build", "-o", mcp_output, "."],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"编译 MCP 主程序失败:\n{result.stderr}")

    # 编译登录工具
    login_src = os.path.join(src, "cmd", "login")
    if os.path.isdir(login_src):
        login_output = os.path.join(MCP_DIR, login_name)
        result = subprocess.run(
            ["go", "build", "-o", login_output, "."],
            cwd=login_src,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"编译登录工具失败:\n{result.stderr}")

    # 设置可执行权限
    if os_name != "windows":
        for name in (mcp_name, login_name):
            path = os.path.join(MCP_DIR, name)
            if os.path.isfile(path):
                os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # 获取 git 版本
    try:
        ver = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=src,
            capture_output=True,
            text=True,
        )
        tag = ver.stdout.strip() or "local-build"
    except Exception:
        tag = "local-build"

    _save_version(tag, "build")
    return tag


# ── 统一安装入口 ──────────────────────────────────────────


def ensure_binary(prefer_source: bool = False, progress_callback=None) -> str:
    """
    确保当前平台的 MCP 二进制可用。

    优先级:
    1. 已存在 → 直接返回
    2. prefer_source=True 且 Go + 源码可用 → 编译
    3. 从 GitHub Releases 下载
    4. Go + 源码可用 → 编译 (fallback)

    Returns:
        版本 tag
    """
    if is_binary_available():
        ver = get_installed_version()
        return ver["tag"] if ver else "unknown"

    if prefer_source and is_go_available() and is_source_available():
        return build_from_source()

    # 尝试下载
    try:
        return download_binary(progress_callback=progress_callback)
    except Exception as download_err:
        # 下载失败，尝试源码编译
        if is_go_available() and is_source_available():
            return build_from_source()
        raise RuntimeError(
            f"无法获取 MCP 二进制:\n"
            f"  下载失败: {download_err}\n"
            f"  源码编译: Go {'✓' if is_go_available() else '✗'}, "
            f"源码 {'✓' if is_source_available() else '✗'}\n\n"
            f"解决方案:\n"
            f"  1. 检查网络后重试: xhs server install\n"
            f"  2. 安装 Go 后从源码编译: xhs server install --from-source\n"
            f"  3. 使用 CDP 模式 (无需 MCP): xhs login --cdp"
        ) from download_err
