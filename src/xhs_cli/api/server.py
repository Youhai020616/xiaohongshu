"""
xhs api — REST API 服务。

提供 HTTP API 接口，封装 MCP/CDP 双引擎。
主要价值：暴露 CDP 独有功能（数据看板/通知）+ 统一接口。

启动方式:
    xhs api start                   # 默认 127.0.0.1:8080
    xhs api start --port 9000       # 指定端口
    xhs api start --host 0.0.0.0    # 允许外部访问
"""
from __future__ import annotations

import json
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "REST API 需要 fastapi 和 uvicorn，请安装:\n"
        "  pip install fastapi uvicorn"
    )

from xhs_cli.engines.cdp_client import CDPClient, CDPError
from xhs_cli.engines.mcp_client import MCPClient, MCPError
from xhs_cli.utils import config

# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------


class SearchRequest(BaseModel):
    keyword: str
    sort_by: str | None = None
    note_type: str | None = None
    publish_time: str | None = None
    search_scope: str | None = None
    location: str | None = None


class PublishRequest(BaseModel):
    title: str = Field(..., max_length=20)
    content: str = Field(..., max_length=1000)
    images: list[str] = Field(default_factory=list)
    video: str | None = None
    tags: list[str] = Field(default_factory=list)
    visibility: str = "公开可见"
    is_original: bool = False
    schedule_at: str | None = None
    products: list[str] = Field(default_factory=list)


class InteractRequest(BaseModel):
    feed_id: str
    xsec_token: str


class CommentRequest(BaseModel):
    feed_id: str
    xsec_token: str
    content: str


class ReplyRequest(BaseModel):
    feed_id: str
    xsec_token: str
    comment_id: str = ""
    user_id: str = ""
    content: str


class DetailRequest(BaseModel):
    feed_id: str
    xsec_token: str
    load_all_comments: bool = False
    limit: int = 20
    click_more_replies: bool = False
    reply_limit: int = 10
    scroll_speed: str | None = None


class ProfileRequest(BaseModel):
    user_id: str
    xsec_token: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_mcp() -> MCPClient:
    cfg = config.load_config()
    return MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])


def _get_cdp(account: str | None = None) -> CDPClient:
    cfg = config.load_config()
    return CDPClient(
        host=cfg["cdp"]["host"],
        port=cfg["cdp"]["port"],
        account=account,
        headless=True,
        reuse_tab=True,
    )


def _ok(data: Any, message: str = "success") -> dict:
    return {"success": True, "data": data, "message": message}


def _extract_mcp_data(result: Any) -> Any:
    """从 MCP 返回中提取可序列化数据。"""
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            if texts:
                # 尝试将拼接文本解析为 JSON
                combined = "\n".join(texts)
                try:
                    return json.loads(combined)
                except (json.JSONDecodeError, TypeError):
                    pass
                # 单段也尝试解析
                if len(texts) == 1:
                    try:
                        return json.loads(texts[0])
                    except (json.JSONDecodeError, TypeError):
                        pass
                return {"text": combined}
        if "result" in result:
            return _extract_mcp_data(result["result"])
    return result


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

def create_app() -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(
        title="redbook-cli API",
        description="小红书 CLI REST API — 搜索、发布、互动、数据分析",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Auth ──────────────────────────────────────────

    @app.get("/api/v1/login/status")
    def login_status():
        try:
            result = _get_mcp().check_login()
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.get("/api/v1/login/qrcode")
    def login_qrcode():
        try:
            result = _get_mcp().get_qrcode()
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.delete("/api/v1/login/cookies")
    def delete_cookies():
        try:
            result = _get_mcp().delete_cookies()
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── Search ────────────────────────────────────────

    @app.post("/api/v1/search")
    def search_feeds(req: SearchRequest):
        filters = {}
        if req.sort_by:
            filters["sort_by"] = req.sort_by
        if req.note_type:
            filters["note_type"] = req.note_type
        if req.publish_time:
            filters["publish_time"] = req.publish_time
        if req.search_scope:
            filters["search_scope"] = req.search_scope
        if req.location:
            filters["location"] = req.location
        try:
            result = _get_mcp().search(req.keyword, filters=filters or None)
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── Publish ───────────────────────────────────────

    @app.post("/api/v1/publish")
    def publish_content(req: PublishRequest):
        try:
            client = _get_mcp()
            if req.video:
                result = client.publish_video(
                    title=req.title, content=req.content, video=req.video,
                    tags=req.tags or None, visibility=req.visibility,
                    schedule_at=req.schedule_at, products=req.products or None,
                )
            else:
                if not req.images:
                    raise HTTPException(400, "需要提供 images 或 video")
                result = client.publish(
                    title=req.title, content=req.content, images=req.images,
                    tags=req.tags or None, visibility=req.visibility,
                    is_original=req.is_original, schedule_at=req.schedule_at,
                    products=req.products or None,
                )
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── Feed Detail ───────────────────────────────────

    @app.post("/api/v1/feeds/detail")
    def feed_detail(req: DetailRequest):
        try:
            result = _get_mcp().get_feed_detail(
                req.feed_id, req.xsec_token,
                load_all_comments=req.load_all_comments,
                limit=req.limit,
                click_more_replies=req.click_more_replies,
                reply_limit=req.reply_limit,
                scroll_speed=req.scroll_speed,
            )
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── Feeds List ────────────────────────────────────

    @app.get("/api/v1/feeds/list")
    def list_feeds():
        try:
            result = _get_mcp().list_feeds()
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── Interact ──────────────────────────────────────

    @app.post("/api/v1/feeds/like")
    def like_feed(req: InteractRequest, unlike: bool = False):
        try:
            result = _get_mcp().like(req.feed_id, req.xsec_token, unlike=unlike)
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.post("/api/v1/feeds/favorite")
    def favorite_feed(req: InteractRequest, unfavorite: bool = False):
        try:
            result = _get_mcp().favorite(req.feed_id, req.xsec_token, unfavorite=unfavorite)
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.post("/api/v1/feeds/comment")
    def post_comment(req: CommentRequest):
        try:
            result = _get_mcp().comment(req.feed_id, req.xsec_token, req.content)
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.post("/api/v1/feeds/comment/reply")
    def reply_comment(req: ReplyRequest):
        try:
            result = _get_mcp().reply(
                req.feed_id, req.xsec_token,
                req.comment_id, req.user_id, req.content,
            )
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── User ──────────────────────────────────────────

    @app.get("/api/v1/user/me")
    def my_info():
        try:
            result = _get_mcp().get_self_info()
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    @app.post("/api/v1/user/profile")
    def user_profile(req: ProfileRequest):
        try:
            result = _get_mcp().user_profile(req.user_id, req.xsec_token)
            return _ok(_extract_mcp_data(result))
        except MCPError as e:
            raise HTTPException(500, str(e))

    # ── CDP 独有功能 ──────────────────────────────────

    @app.get("/api/v1/analytics")
    def analytics(csv_file: str | None = None, page_size: int = 10, account: str | None = None):
        """创作者数据看板 (仅 CDP)。"""
        try:
            result = _get_cdp(account).content_data(csv_file=csv_file, page_size=page_size)
            return _ok(result)
        except CDPError as e:
            raise HTTPException(500, str(e))

    @app.get("/api/v1/notifications")
    def notifications(wait: float = 18.0, account: str | None = None):
        """通知消息 (仅 CDP)。"""
        try:
            result = _get_cdp(account).notifications(wait_seconds=wait)
            return _ok(result)
        except CDPError as e:
            raise HTTPException(500, str(e))

    # ── Health ────────────────────────────────────────

    @app.get("/health")
    def health():
        cfg = config.load_config()
        mcp_running = MCPClient.is_running(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
        return {"status": "ok", "mcp": "running" if mcp_running else "stopped"}

    return app
