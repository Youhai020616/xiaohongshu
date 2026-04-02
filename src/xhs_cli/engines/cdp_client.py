"""
CDP Client — 封装现有 CDP Python 脚本的调用。

通过 subprocess 调用现有脚本，保持向后兼容。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(_PROJECT_ROOT, "scripts")
CDP_SCRIPT = os.path.join(SCRIPTS_DIR, "cdp_publish.py")
PIPELINE_SCRIPT = os.path.join(SCRIPTS_DIR, "publish_pipeline.py")
CHROME_LAUNCHER = os.path.join(SCRIPTS_DIR, "chrome_launcher.py")


class CDPError(Exception):
    """CDP 调用错误。"""


class CDPClient:
    """
    CDP 脚本封装客户端。

    通过 subprocess 调用 cdp_publish.py / publish_pipeline.py 等脚本，
    解析输出并返回结构化数据。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9222,
        account: str | None = None,
        headless: bool = False,
        reuse_tab: bool = True,
    ):
        self.host = host
        self.port = port
        self.account = account
        self.headless = headless
        self.reuse_tab = reuse_tab

    def _base_args(self) -> list[str]:
        """构建 cdp_publish.py 的基础参数。"""
        args = [sys.executable, CDP_SCRIPT, "--host", self.host, "--port", str(self.port)]
        if self.account:
            args.extend(["--account", self.account])
        if self.headless:
            args.append("--headless")
        if self.reuse_tab:
            args.append("--reuse-existing-tab")
        return args

    def _run(self, cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        """执行命令，返回结果。"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=SCRIPTS_DIR,
                env={**os.environ, "PYTHONPATH": SCRIPTS_DIR},
            )
            return result
        except subprocess.TimeoutExpired:
            raise CDPError(f"命令执行超时 ({timeout}s)")

    def _extract_json(self, output: str, marker: str) -> dict[str, Any]:
        """从输出中提取 JSON 数据（marker 后面的部分）。"""
        lines = output.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if marker in line:
                json_start = i + 1
                break
        if json_start is None:
            return {}

        json_text = "\n".join(lines[json_start:])
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # Chrome lifecycle
    # ------------------------------------------------------------------

    def start_chrome(self) -> bool:
        """启动 Chrome 浏览器。"""
        cmd = [sys.executable, CHROME_LAUNCHER, "--port", str(self.port)]
        if self.headless:
            cmd.append("--headless")
        if self.account:
            cmd.extend(["--account", self.account])
        result = self._run(cmd, timeout=30)
        return result.returncode == 0

    def stop_chrome(self) -> bool:
        """关闭 Chrome 浏览器。"""
        cmd = [sys.executable, CHROME_LAUNCHER, "--kill"]
        result = self._run(cmd, timeout=15)
        return result.returncode == 0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def check_login(self) -> bool:
        """检查登录状态。"""
        cmd = self._base_args() + ["check-login"]
        result = self._run(cmd, timeout=30)
        return result.returncode == 0

    def login(self) -> str:
        """打开登录页面（需要有头模式扫码）。

        Raises:
            CDPError: Chrome 启动失败或登录页面无法打开。
        """
        args = [sys.executable, CDP_SCRIPT, "--host", self.host, "--port", str(self.port)]
        if self.account:
            args.extend(["--account", self.account])
        # login 强制有头模式
        args.append("login")
        result = self._run(args, timeout=60)
        if result.returncode != 0:
            err_detail = result.stderr.strip() or result.stdout.strip() or "未知错误"
            raise CDPError(f"登录页面打开失败: {err_detail}")
        return result.stdout

    # ------------------------------------------------------------------
    # Search (带推荐词，MCP 不支持)
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str,
        sort_by: str | None = None,
        note_type: str | None = None,
        publish_time: str | None = None,
    ) -> dict[str, Any]:
        """搜索笔记，返回包含推荐词的完整结果。"""
        cmd = self._base_args() + ["search-feeds", "--keyword", keyword]
        if sort_by:
            cmd.extend(["--sort-by", sort_by])
        if note_type:
            cmd.extend(["--note-type", note_type])
        if publish_time:
            cmd.extend(["--publish-time", publish_time])

        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"搜索失败: {result.stderr}")
        return self._extract_json(result.stdout, "SEARCH_FEEDS_RESULT:")

    # ------------------------------------------------------------------
    # Feed detail
    # ------------------------------------------------------------------

    def get_feed_detail(self, feed_id: str, xsec_token: str) -> dict[str, Any]:
        """获取笔记详情。"""
        cmd = self._base_args() + [
            "get-feed-detail",
            "--feed-id",
            feed_id,
            "--xsec-token",
            xsec_token,
        ]
        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"获取详情失败: {result.stderr}")
        return self._extract_json(result.stdout, "GET_FEED_DETAIL_RESULT:")

    # ------------------------------------------------------------------
    # Comment
    # ------------------------------------------------------------------

    def comment(self, feed_id: str, xsec_token: str, content: str) -> dict[str, Any]:
        """发表评论。"""
        cmd = self._base_args() + [
            "post-comment-to-feed",
            "--feed-id",
            feed_id,
            "--xsec-token",
            xsec_token,
            "--content",
            content,
        ]
        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"评论失败: {result.stderr}")
        return self._extract_json(result.stdout, "POST_COMMENT_RESULT:")

    # ------------------------------------------------------------------
    # Like & Favorite (MCP 回退)
    # ------------------------------------------------------------------

    def like(self, feed_id: str, xsec_token: str, unlike: bool = False) -> dict[str, Any]:
        """点赞笔记。

        注意：CDP 模式下 unlike（取消点赞）暂不支持，传 unlike=True 会抛出异常。
        """
        if unlike:
            raise CDPError("CDP 模式暂不支持取消点赞，请使用 MCP 引擎")
        cmd = self._base_args() + [
            "like-note",
            "--feed-id",
            feed_id,
            "--xsec-token",
            xsec_token,
        ]
        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"点赞失败: {result.stderr}")
        return self._extract_json(result.stdout, "LIKE_NOTE_RESULT:")

    def favorite(self, feed_id: str, xsec_token: str, unfavorite: bool = False) -> dict[str, Any]:
        """收藏笔记。

        注意：CDP 模式下 unfavorite（取消收藏）暂不支持，传 unfavorite=True 会抛出异常。
        """
        if unfavorite:
            raise CDPError("CDP 模式暂不支持取消收藏，请使用 MCP 引擎")
        cmd = self._base_args() + [
            "collect-note",
            "--feed-id",
            feed_id,
            "--xsec-token",
            xsec_token,
        ]
        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"收藏失败: {result.stderr}")
        return self._extract_json(result.stdout, "COLLECT_NOTE_RESULT:")

    # ------------------------------------------------------------------
    # Analytics (MCP 不支持)
    # ------------------------------------------------------------------

    def content_data(self, csv_file: str | None = None, page_size: int = 10) -> dict[str, Any]:
        """获取数据看板。"""
        cmd = self._base_args() + ["content-data", "--page-size", str(page_size)]
        if csv_file:
            cmd.extend(["--csv-file", csv_file])
        result = self._run(cmd, timeout=60)
        if result.returncode != 0:
            raise CDPError(f"获取数据看板失败: {result.stderr}")
        return self._extract_json(result.stdout, "CONTENT_DATA_RESULT:")

    # ------------------------------------------------------------------
    # Notifications (MCP 不支持)
    # ------------------------------------------------------------------

    def notifications(self, wait_seconds: float = 18.0) -> dict[str, Any]:
        """获取通知。"""
        cmd = self._base_args() + [
            "get-notification-mentions",
            "--wait-seconds",
            str(wait_seconds),
        ]
        result = self._run(cmd, timeout=int(wait_seconds) + 30)
        if result.returncode != 0:
            raise CDPError(f"获取通知失败: {result.stderr}")
        return self._extract_json(result.stdout, "GET_NOTIFICATION_MENTIONS_RESULT:")

    # ------------------------------------------------------------------
    # Publish (via pipeline)
    # ------------------------------------------------------------------

    def publish(
        self,
        title: str,
        content: str,
        images: list[str] | None = None,
        image_urls: list[str] | None = None,
        video: str | None = None,
        video_url: str | None = None,
        auto_publish: bool = True,
    ) -> str:
        """通过 CDP 流水线发布内容。"""
        cmd = [
            sys.executable,
            PIPELINE_SCRIPT,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--title",
            title,
            "--content",
            content,
        ]
        if self.headless:
            cmd.append("--headless")
        if self.account:
            cmd.extend(["--account", self.account])
        if self.reuse_tab:
            cmd.append("--reuse-existing-tab")

        if video:
            cmd.extend(["--video", video])
        elif video_url:
            cmd.extend(["--video-url", video_url])
        elif image_urls:
            cmd.extend(["--image-urls"] + image_urls)
        elif images:
            cmd.extend(["--images"] + images)
        else:
            raise CDPError("发布需要图片或视频")

        if auto_publish:
            cmd.append("--auto-publish")

        result = self._run(cmd, timeout=180)
        if result.returncode != 0:
            raise CDPError(f"发布失败: {result.stderr.strip() or result.stdout.strip() or '未知错误'}")
        return result.stdout

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def list_accounts(self) -> str:
        cmd = self._base_args() + ["list-accounts"]
        result = self._run(cmd, timeout=15)
        return result.stdout

    def add_account(self, name: str, alias: str | None = None) -> str:
        cmd = self._base_args() + ["add-account", name]
        if alias:
            cmd.extend(["--alias", alias])
        result = self._run(cmd, timeout=15)
        return result.stdout

    def remove_account(self, name: str, delete_profile: bool = False) -> str:
        cmd = self._base_args() + ["remove-account", name]
        if delete_profile:
            cmd.append("--delete-profile")
        result = self._run(cmd, timeout=15)
        return result.stdout
