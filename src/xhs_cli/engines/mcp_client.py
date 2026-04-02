"""
MCP Client — 封装小红书 MCP Server 的 JSON-RPC 调用。

自动管理 Session 生命周期，用户无需手动处理 initialize / session-id。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from typing import Any

import requests

from xhs_cli.engines.mcp_binary import (
    MCP_DIR,
    get_binary_path,
    get_login_binary_path,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18060
DEFAULT_PROXY = ""
SESSION_TIMEOUT = 10  # seconds


def _is_wsl_env() -> bool:
    """Lightweight WSL detection for timeout adjustments."""
    if "WSL_DISTRO_NAME" in os.environ:
        return True
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version") as f:
                content = f.read().lower()
                return "microsoft" in content or "wsl" in content
    except Exception:
        pass
    return False


# 路径统一由 mcp_binary 模块管理
MCP_LOG_FILE = os.path.join(MCP_DIR, "mcp.log")
MCP_COOKIES_FILE = os.path.join(MCP_DIR, "cookies.json")
MCP_BINARY = get_binary_path()
MCP_LOGIN_BINARY = get_login_binary_path()


class MCPError(Exception):
    """MCP 调用错误。"""


class MCPClient:
    """
    小红书 MCP Server 客户端。

    自动处理 session 初始化，提供高层方法封装所有 MCP 工具。
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/mcp"
        self.session_id: str | None = None
        self._call_id = 0
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _ensure_session(self):
        """初始化 MCP session（如果尚未初始化）。"""
        if self.session_id:
            return

        # Step 1: initialize
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "xhs-cli", "version": "1.0"},
            },
        }
        try:
            resp = requests.post(
                self.base_url,
                headers=self._headers,
                json=payload,
                timeout=SESSION_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise MCPError(f"无法连接 MCP 服务 ({self.base_url}): {e}")

        self.session_id = resp.headers.get("Mcp-Session-Id")
        if not self.session_id:
            raise MCPError("MCP 服务未返回 Session ID")

        # Step 2: send initialized notification
        self._notify("notifications/initialized")

    def _next_id(self) -> int:
        self._call_id += 1
        return self._call_id

    def _notify(self, method: str):
        """发送 JSON-RPC notification（无 id）。"""
        payload = {"jsonrpc": "2.0", "method": method}
        headers = {**self._headers, "Mcp-Session-Id": self.session_id}
        try:
            requests.post(self.base_url, headers=headers, json=payload, timeout=SESSION_TIMEOUT)
        except requests.RequestException:
            # 通知是尽力而为，失败不影响主流程，防止 session 半初始化崩溃
            pass

    # ------------------------------------------------------------------
    # Low-level call
    # ------------------------------------------------------------------

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None, timeout: int = 120) -> Any:
        """
        调用 MCP 工具，返回结果。

        自动处理 session 初始化、失效恢复和错误。
        Session 失效时（4xx / 连接错误）自动重置并重试一次。
        """
        for attempt in range(2):
            self._ensure_session()

            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {},
                },
            }
            headers = {**self._headers, "Mcp-Session-Id": self.session_id}

            try:
                resp = requests.post(self.base_url, headers=headers, json=payload, timeout=timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                # 连接失败时，首次尝试重置 session 后重试
                if attempt == 0:
                    self.session_id = None
                    continue
                raise MCPError(f"MCP 服务连接失败: {e}")
            except requests.RequestException as e:
                raise MCPError(f"MCP 调用失败 ({tool_name}): {e}")

            # Session 失效时（4xx 错误），重置 session 后重试一次
            if resp.status_code >= 400 and attempt == 0:
                self.session_id = None
                continue

            if resp.status_code >= 400:
                raise MCPError(f"MCP 调用失败 ({tool_name}): HTTP {resp.status_code}")

            # Handle 204 No Content or empty body
            if resp.status_code == 204 or not resp.text.strip():
                return None

            # Parse SSE response or JSON
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return self._parse_sse(resp.text)
            else:
                try:
                    data = resp.json()
                except (ValueError, json.JSONDecodeError):
                    raise MCPError(f"MCP 返回无效 JSON ({tool_name}): {resp.text[:200]}")
                if "error" in data:
                    raise MCPError(f"MCP 错误: {data['error']}")
                return data.get("result", data)

        # 理论上不会到达这里，但作为安全兜底
        raise MCPError(f"MCP 调用失败 ({tool_name}): 重试耗尽")

    def _parse_sse(self, text: str) -> Any:
        """解析 SSE 响应，提取最后一个 data 事件。"""
        last_data = None
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                raw = line[5:].strip()
                if raw:
                    try:
                        last_data = json.loads(raw)
                    except json.JSONDecodeError:
                        last_data = raw
        return last_data

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def is_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
        """检查 MCP 服务是否正在运行（仅检测连通性，不创建孤立 session）。"""
        try:
            requests.get(f"http://{host}:{port}/mcp", timeout=3)
            # MCP 服务通常对 GET 返回 405 等状态码，只要不是连接错误就说明在运行
            return True
        except Exception:
            return False

    @staticmethod
    def start_server(port: int = DEFAULT_PORT, proxy: str = DEFAULT_PROXY) -> bool:
        """启动 MCP 服务（后台运行）。"""
        if MCPClient.is_running(port=port):
            return True

        if not os.path.isfile(MCP_BINARY):
            raise MCPError(f"MCP 二进制文件不存在: {MCP_BINARY}")

        os.makedirs(os.path.dirname(MCP_LOG_FILE), exist_ok=True)

        # 代理通过 XHS_PROXY 环境变量传递 (Go 二进制不接受 -rod flag)
        env = {**os.environ, "COOKIES_PATH": MCP_COOKIES_FILE}
        if proxy:
            env["XHS_PROXY"] = proxy

        # WSL: 传递 no-sandbox 标志给 Go 端 go-rod
        if _is_wsl_env():
            env["XHS_NO_SANDBOX"] = "1"

        cmd = [MCP_BINARY, "-port", f":{port}"]

        # 跨平台后台进程创建
        popen_kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": env,
            "cwd": os.path.dirname(MCP_BINARY),
        }

        # 不使用 with 语句，避免句柄提前关闭导致后台进程丢失日志
        log = open(MCP_LOG_FILE, "a")
        popen_kwargs["stdout"] = log
        popen_kwargs["stderr"] = log

        if sys.platform == "win32":
            # Windows: 隐藏控制台窗口，分离进程
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            popen_kwargs["creationflags"] = CREATE_NO_WINDOW | DETACHED_PROCESS
        else:
            # macOS / Linux: 新会话，脱离终端
            popen_kwargs["start_new_session"] = True

        subprocess.Popen(cmd, **popen_kwargs)

        # 子进程已继承 fd，父进程端可以安全关闭，避免文件描述符泄漏
        log.close()

        # Wait for startup — WSL/低配环境需要更长时间
        max_wait = 45 if _is_wsl_env() else 15
        for _ in range(max_wait):
            time.sleep(1)
            if MCPClient.is_running(port=port):
                return True

        wsl_hint = "\n  WSL 环境建议: 确保已安装 Chromium (sudo apt install chromium-browser)" if _is_wsl_env() else ""
        raise MCPError(f"MCP 服务启动超时 ({max_wait}s)。{wsl_hint}")

    @staticmethod
    def _find_mcp_pids() -> list[int]:
        """跨平台查找 MCP 进程 PID。"""
        pids = []
        binary_name = os.path.basename(MCP_BINARY)
        my_pid = os.getpid()
        try:
            if sys.platform == "win32":
                # Windows: wmic 查找精确的进程名
                result = subprocess.run(
                    ["wmic", "process", "where", f"Name='{binary_name}'", "get", "ProcessId", "/format:csv"],
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or line.startswith("Node"):
                        continue
                    parts = line.split(",")
                    # CSV 格式: Node,ProcessId
                    pid_str = parts[-1].strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid != my_pid:
                            pids.append(pid)
            else:
                # macOS / Linux: pgrep 精确匹配二进制名称
                # 使用 -x 精确匹配进程名，避免匹配 Python 自身进程
                result = subprocess.run(
                    ["pgrep", "-x", binary_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    # -x 匹配失败时回退到 -f 但排除自身
                    result = subprocess.run(
                        ["pgrep", "-f", binary_name],
                        capture_output=True,
                        text=True,
                    )
                for pid_str in result.stdout.strip().split("\n"):
                    pid_str = pid_str.strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid != my_pid:
                            pids.append(pid)
        except Exception:
            pass
        return pids

    @staticmethod
    def stop_server() -> bool:
        """停止 MCP 服务。"""
        pids = MCPClient._find_mcp_pids()
        if not pids:
            return True
        try:
            for pid in pids:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)

            # 等待进程实际退出（WSL 下清理可能较慢）
            for _ in range(10):
                time.sleep(0.5)
                remaining = MCPClient._find_mcp_pids()
                if not remaining:
                    return True

            # SIGTERM 未生效，强制 SIGKILL
            remaining = MCPClient._find_mcp_pids()
            for pid in remaining:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
                    else:
                        os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            time.sleep(1)
            return not MCPClient._find_mcp_pids()
        except Exception:
            return False

    @staticmethod
    def get_server_pid() -> int | None:
        """获取 MCP 服务进程 PID。"""
        pids = MCPClient._find_mcp_pids()
        return pids[0] if pids else None

    # ------------------------------------------------------------------
    # High-level tool wrappers
    # ------------------------------------------------------------------

    def check_login(self) -> dict:
        return self.call_tool("check_login_status")

    def get_qrcode(self, timeout: int = 600) -> dict:
        """获取登录二维码。浏览器启动较慢（尤其 WSL），默认 600s 超时。"""
        return self.call_tool("get_login_qrcode", timeout=timeout)

    def delete_cookies(self) -> dict:
        return self.call_tool("delete_cookies")

    def publish(
        self,
        title: str,
        content: str,
        images: list[str],
        tags: list[str] | None = None,
        visibility: str = "公开可见",
        is_original: bool = False,
        schedule_at: str | None = None,
        products: list[str] | None = None,
    ) -> dict:
        args: dict[str, Any] = {
            "title": title,
            "content": content,
            "images": images,
        }
        if tags:
            args["tags"] = tags
        if visibility != "公开可见":
            args["visibility"] = visibility
        if is_original:
            args["is_original"] = True
        if schedule_at:
            args["schedule_at"] = schedule_at
        if products:
            args["products"] = products
        return self.call_tool("publish_content", args)

    def publish_video(
        self,
        title: str,
        content: str,
        video: str,
        tags: list[str] | None = None,
        visibility: str = "公开可见",
        schedule_at: str | None = None,
        products: list[str] | None = None,
    ) -> dict:
        args: dict[str, Any] = {
            "title": title,
            "content": content,
            "video": video,
        }
        if tags:
            args["tags"] = tags
        if visibility != "公开可见":
            args["visibility"] = visibility
        if schedule_at:
            args["schedule_at"] = schedule_at
        if products:
            args["products"] = products
        return self.call_tool("publish_with_video", args)

    def search(self, keyword: str, filters: dict | None = None) -> dict:
        args: dict[str, Any] = {"keyword": keyword}
        if filters:
            args["filters"] = filters
        return self.call_tool("search_feeds", args)

    def get_feed_detail(
        self,
        feed_id: str,
        xsec_token: str,
        load_all_comments: bool = False,
        limit: int = 20,
        click_more_replies: bool = False,
        reply_limit: int = 10,
        scroll_speed: str | None = None,
    ) -> dict:
        args: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
        if load_all_comments:
            args["load_all_comments"] = True
            args["limit"] = limit
            args["click_more_replies"] = click_more_replies
            args["reply_limit"] = reply_limit
            if scroll_speed:
                args["scroll_speed"] = scroll_speed
        # 全量评论加载需要更长超时
        timeout = 180 if load_all_comments else 120
        return self.call_tool("get_feed_detail", args, timeout=timeout)

    def comment(self, feed_id: str, xsec_token: str, content: str) -> dict:
        return self.call_tool(
            "post_comment_to_feed",
            {
                "feed_id": feed_id,
                "xsec_token": xsec_token,
                "content": content,
            },
        )

    def reply(self, feed_id: str, xsec_token: str, comment_id: str, user_id: str, content: str) -> dict:
        return self.call_tool(
            "reply_comment_in_feed",
            {
                "feed_id": feed_id,
                "xsec_token": xsec_token,
                "comment_id": comment_id,
                "user_id": user_id,
                "content": content,
            },
        )

    def like(self, feed_id: str, xsec_token: str, unlike: bool = False) -> dict:
        args: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
        if unlike:
            args["unlike"] = True
        return self.call_tool("like_feed", args)

    def favorite(self, feed_id: str, xsec_token: str, unfavorite: bool = False) -> dict:
        args: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
        if unfavorite:
            args["unfavorite"] = True
        return self.call_tool("favorite_feed", args)

    def list_feeds(self) -> dict:
        return self.call_tool("list_feeds")

    def user_profile(self, user_id: str, xsec_token: str) -> dict:
        return self.call_tool("user_profile", {"user_id": user_id, "xsec_token": xsec_token})

    def get_self_info(self) -> dict:
        return self.call_tool("check_login_status")
