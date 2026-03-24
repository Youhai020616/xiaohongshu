# 📋 redbook-cli 功能补齐计划

> 基于 `sources/xiaohongshu-mcp` 参考项目的对比分析，补齐缺失功能。
>
> **核心原则**：所有改动都是在现有架构（CLI → MCPClient/CDPClient → 后端）上增量扩展，不重写。

---

## 架构速览（改动前必读）

```
CLI (Click commands)
  ├── src/xhs_cli/commands/*.py      ← 命令层，接受用户输入
  ├── src/xhs_cli/engines/
  │   ├── mcp_client.py              ← MCP 高层封装（call_tool → search_feeds 等）
  │   └── cdp_client.py              ← CDP subprocess 封装
  └── src/xhs_cli/utils/
      ├── config.py                  ← ~/.xhs/config.json
      ├── index_cache.py             ← 短索引
      ├── output.py                  ← Rich 美化输出
      └── export.py                  ← CSV/JSON 导出
```

**改动模式**（每个功能都遵循）：
1. `mcp_client.py` 增加高层方法（透传参数到 MCP Server Go 二进制已有的工具）
2. `commands/*.py` 增加 Click option 暴露给用户
3. 必要时更新 `output.py` 美化输出

**关键事实**：MCP Go Server 已内置这些工具参数（`products`, `search_scope`, `location`, `load_all_comments` 等），只是 Python CLI 层没有暴露。所以大部分改动只需要在 Python 层打通参数透传。

---

## Phase 1: 搜索增强（P0，预估 1h）

### 1.1 MCP 搜索高级过滤

**现状**：`_search_mcp` 仅传 `keyword` + `sort`，Go Server 的 `SearchFeedsArgs.Filters` 支持 5 个字段但只用了 1 个。

**目标**：暴露全部搜索过滤参数。

**改动文件**：

#### ① `src/xhs_cli/commands/search.py`

在 `search` 命令增加 Click options：

```python
# 新增 options
@click.option("--scope", type=click.Choice(["不限", "已看过", "未看过", "已关注"]),
              default=None, help="搜索范围")
@click.option("--location", type=click.Choice(["不限", "同城", "附近"]),
              default=None, help="位置距离")
```

修改 `_search_mcp` 函数，构建完整 filters：

```python
def _search_mcp(cfg, keyword, sort, note_type, pub_time, scope, location, as_json, output):
    client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
    filters = {}
    if sort:
        filters["sort_by"] = sort          # 注意：Go 端字段名是 sort_by
    if note_type:
        filters["note_type"] = note_type
    if pub_time:
        filters["publish_time"] = pub_time
    if scope:
        filters["search_scope"] = scope
    if location:
        filters["location"] = location
    result = client.search(keyword, filters=filters or None)
    # ... 后续不变
```

同时修改主 `search()` 函数签名，将 `note_type`, `pub_time` 也传给 `_search_mcp`（目前只传了 CDP）。

#### ② `src/xhs_cli/engines/mcp_client.py`

`search()` 方法无需改动 — 已经透传 `filters` dict。Go 端会自动解析。

**验证**：`xhs search "美食" --sort 最多点赞 --scope 已关注 --location 同城`

---

## Phase 2: 发布增强 — 商品绑定（P0，预估 0.5h）

### 2.1 publish 命令增加 products 参数

**现状**：Go Server `PublishContentArgs` 已有 `Products []string` 字段，CLI 未暴露。

**改动文件**：

#### ① `src/xhs_cli/commands/publish.py`

```python
# 新增 option
@click.option("--products", multiple=True, help="商品关键词 (可多个，如: --products 面膜 --products 防晒霜)")
```

在 `_publish_mcp` 中传入：

```python
def _publish_mcp(cfg, title, content, images, video, tags, visibility, original, schedule, products):
    # ... existing code ...
    if video:
        client.publish_video(..., products=products or None)
    else:
        client.publish(..., products=products or None)
```

#### ② `src/xhs_cli/engines/mcp_client.py`

`publish()` 和 `publish_video()` 方法增加 `products` 参数：

```python
def publish(self, ..., products: list[str] | None = None) -> dict:
    # ...
    if products:
        args["products"] = products
    return self.call_tool("publish_content", args)

def publish_video(self, ..., products: list[str] | None = None) -> dict:
    # ...
    if products:
        args["products"] = products
    return self.call_tool("publish_with_video", args)
```

**验证**：`xhs publish -t "好物推荐" -c "真的很好用" -i img.jpg --products 面膜 --products 防晒霜`

---

## Phase 3: 评论深度控制（P1，预估 1h）

### 3.1 detail 命令增加评论控制参数

**现状**：`get_feed_detail` 仅传 `load_all_comments` bool，Go 端支持 5 个额外参数。

**改动文件**：

#### ① `src/xhs_cli/commands/search.py` — `detail` 命令

```python
@click.command("detail", help="查看笔记详情")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--comments", is_flag=True, help="加载全部评论")
@click.option("--comment-limit", type=int, default=20, help="最多加载评论数 (默认 20)")
@click.option("--expand-replies", is_flag=True, help="展开子评论")
@click.option("--reply-limit", type=int, default=10, help="跳过回复数超过此值的评论 (默认 10)")
@click.option("--scroll-speed", type=click.Choice(["slow", "normal", "fast"]),
              default=None, help="评论滚动速度")
# ... 其他现有 options
```

#### ② `src/xhs_cli/engines/mcp_client.py`

扩展 `get_feed_detail()` 签名：

```python
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
    args = {"feed_id": feed_id, "xsec_token": xsec_token}
    if load_all_comments:
        args["load_all_comments"] = True
        args["limit"] = limit
        args["click_more_replies"] = click_more_replies
        args["reply_limit"] = reply_limit
        if scroll_speed:
            args["scroll_speed"] = scroll_speed
    return self.call_tool("get_feed_detail", args, timeout=180)  # 全量加载需更长超时
```

**验证**：`xhs detail 1 --comments --comment-limit 50 --expand-replies --scroll-speed slow`

---

## Phase 4: 智能互动状态检测（P1，预估 1h）

### 4.1 点赞/收藏前自动检测状态

**现状**：CLI 直接调用 `like_feed` / `favorite_feed`，不检测当前状态。Go 端已有智能检测（已点赞则跳过），但 CLI 层没有向用户反馈。

**分析**：Go 端 `handleLikeFeed` 已内置状态检测。CLI 层需要做的是 **解析返回文本**，向用户展示检测结果。

**改动文件**：

#### ① `src/xhs_cli/commands/interact.py`

```python
@click.command("like", help="点赞笔记 (支持短索引: xhs like 1)")
@click.argument("feed_id")
@click.option("--token", "-t", default=None, help="xsec_token")
@click.option("--unlike", is_flag=True, help="取消点赞")
def like(feed_id, token, unlike):
    feed_id, token = _resolve_feed(feed_id, token or "")
    action = "取消点赞" if unlike else "点赞"
    info(f"正在{action}...")

    try:
        result = _get_mcp().like(feed_id, token, unlike=unlike)
        text = _extract_result_text(result)
        if "跳过" in text or "已" in text:
            info(f"智能检测: {text}")  # 已点赞 → 跳过
        else:
            success(f"{action}成功 👍")
    except MCPError as e:
        error(f"{action}失败: {e}")
        raise SystemExit(1)
```

新增 `_extract_result_text()` 辅助函数（从 MCP 返回中提取文本，复用 profile.py 的模式）。

对 `favorite` 命令做同样处理。

**验证**：对已点赞笔记执行 `xhs like 1`，应显示"智能检测: 已点赞，跳过"。

---

## Phase 5: delete_cookies 工具（P2，预估 0.5h）

### 5.1 新增 `xhs reset-login` 命令

**现状**：Go Server 已有 `delete_cookies` 工具，CLI 未暴露。

**改动文件**：

#### ① `src/xhs_cli/engines/mcp_client.py`

```python
def delete_cookies(self) -> dict:
    return self.call_tool("delete_cookies")
```

#### ② `src/xhs_cli/commands/auth.py`

```python
@click.command("reset-login", help="重置登录状态 (删除 Cookies)")
@click.confirmation_option(prompt="确定要重置登录状态吗？重置后需要重新登录。")
def reset_login():
    """删除 Cookies 文件，重置登录状态。"""
    cfg = config.load_config()
    client = MCPClient(host=cfg["mcp"]["host"], port=cfg["mcp"]["port"])
    info("正在重置登录状态...")
    try:
        client.delete_cookies()
        success("登录状态已重置，请运行 xhs login 重新登录")
    except MCPError as e:
        error(f"重置失败: {e}")
        raise SystemExit(1)
```

#### ③ `src/xhs_cli/main.py`

```python
from xhs_cli.commands.auth import auth_status, login, logout, reset_login
cli.add_command(reset_login)
```

**验证**：`xhs reset-login` → 确认提示 → 删除成功 → `xhs login` 重新登录。

---

## Phase 6: Docker 支持（P2，预估 1.5h）

### 6.1 新增 Dockerfile + docker-compose

**目标**：用户一键 `docker compose up` 运行完整服务。

**新增文件**：

#### ① `Dockerfile`

```dockerfile
FROM python:3.11-slim

# 安装 Chrome (CDP 需要)
RUN apt-get update && apt-get install -y \
    chromium chromium-driver fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

# MCP 二进制
COPY mcp/xiaohongshu-mcp-linux-amd64 /app/mcp/xiaohongshu-mcp-linux-amd64
RUN chmod +x /app/mcp/xiaohongshu-mcp-linux-amd64

EXPOSE 18060 9222
CMD ["xhs", "server", "start", "--foreground"]
```

#### ② `docker-compose.yml`

```yaml
version: "3.8"
services:
  redbook-cli:
    build: .
    ports:
      - "18060:18060"
      - "9222:9222"
    volumes:
      - ./data/cookies:/root/.xhs
      - ./data/images:/app/images
    environment:
      - XHS_PROXY=${XHS_PROXY:-}
    restart: unless-stopped
```

> **前置条件**：需要获取 Linux amd64 的 MCP 二进制文件。当前 `mcp/` 目录仅有 darwin-arm64。
> 可从参考项目 releases 下载，或者交叉编译。

---

## Phase 7: REST API（P3，预估 3h）

### 7.1 新增 HTTP API 层

**目标**：提供 `/api/v1/*` REST API，让非 CLI 场景也能调用。

**新增文件**：`src/xhs_cli/api/` 目录

这是**最大**的改动，涉及新增一个 FastAPI/Flask 服务。优先级最低，在 Phase 1-6 完成后考虑。

**初步方案**：

```
src/xhs_cli/api/
├── __init__.py
├── server.py          ← FastAPI app
├── routes/
│   ├── auth.py
│   ├── publish.py
│   ├── search.py
│   └── interact.py
```

CLI 增加 `xhs api start` 命令启动 HTTP API 服务。内部复用 MCPClient/CDPClient。

> **决策点**：是否真的需要？你的项目已经通过 CLI + MCP Skill 覆盖了 AI Agent 场景。REST API 主要价值在 Web 前端集成。

---

## 实施总览

| Phase | 功能 | 优先级 | 改动文件数 | 预估时间 | 状态 |
|:-----:|------|:------:|:----------:|:--------:|:----:|
| 1 | 搜索高级过滤 (+scope/location, 修复 sort_by bug) | P0 | 1 | 1h | ✅ Done |
| 2 | 商品绑定/带货 (+products) | P0 | 2 | 0.5h | ✅ Done |
| 3 | 评论深度控制 (+comment-limit/expand-replies/scroll-speed) | P1 | 2 | 1h | ✅ Done |
| 4 | 智能互动状态反馈 (解析+展示 MCP 返回) | P1 | 1 | 1h | ✅ Done |
| 5 | reset-login 命令 (带确认提示) | P2 | 3 | 0.5h | ✅ Done |
| 6 | Docker (Dockerfile + docker-compose + README) | P2 | 3 (新文件) | 1.5h | ✅ Done |
| 7 | REST API (FastAPI, 可选依赖) | P3 | 4 (新模块) | 3h | ✅ Done |
| | **总计** | | | **~8.5h** | **全部完成** |

---

## 执行顺序建议

```
Phase 1 (搜索) → Phase 2 (发布) → Phase 3 (评论) → Phase 4 (互动)
                                                          ↓
                                           Phase 5 (cookies) → Phase 6 (Docker)
                                                                      ↓
                                                               Phase 7 (API, 可选)
```

**Phase 1-3 是纯参数透传**，改动最小、风险最低、价值最高，建议一口气做完。
**Phase 4** 需要理解 Go 端返回格式，建议先手动调用 MCP 工具观察返回值。
**Phase 5** 独立小功能，随时可插入。
**Phase 6-7** 是工程基建，不影响核心功能，按需推进。

---

## 不做的功能（及理由）

| 功能 | 理由 |
|------|------|
| 跨平台 MCP 二进制 | Go 交叉编译属于上游问题，不在 CLI 层解决 |
| 浏览器插件版 (x-mcp) | 完全不同的产品形态 |
| Openclaw Skills 分包 | 已有 SKILL.md，不需要额外分包 |

---

*Created: 2026-03-24*
*Last Updated: 2026-03-24*
