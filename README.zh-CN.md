# 📕 xiaohongshu

> AI 驱动的小红书自动化工具 — 发布、搜索、互动、数据分析一站式搞定。

[English](./README.md) | 中文

## 这是什么？

一套完整的小红书自动化工具包，包含两套互补引擎：

| 引擎 | 技术栈 | 适用场景 | 启动方式 |
|------|--------|---------|---------|
| **MCP 服务** | Go 编译二进制, JSON-RPC | 发布、搜索、评论、点赞 | 常驻后台 |
| **CDP 脚本** | Python, Chrome DevTools | 数据看板、通知、高级搜索 | 按需启动 |

可作为 [OpenClaw](https://github.com/openclaw/openclaw) Skill 使用，也可独立运行或接入任何 MCP 兼容客户端（Claude Code、Cursor 等）。

## 核心功能

- 📝 **发布** — 图文/视频，支持标签、定时发布、可见范围设置
- 🔍 **搜索** — 关键词搜索，支持排序、类型过滤、搜索推荐词
- 💬 **互动** — 评论、回复、点赞、收藏
- 👤 **用户** — 获取任意用户主页和笔记
- 📊 **数据** — 创作者后台数据导出（CSV）
- 🔔 **通知** — 获取@提及和互动通知
- 👥 **多账号** — 独立 Chrome Profile 隔离
- 🔐 **扫码登录** — 二维码登录 + Cookie 持久化

## 快速开始

### 环境要求

- macOS Apple Silicon（MCP 二进制目前仅支持 darwin-arm64）
- Python 3.9+（CDP 脚本）
- Google Chrome（CDP 脚本和扫码登录）

### 1. 克隆项目

```bash
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu
```

### 2. 启动 MCP 服务

```bash
cd mcp
chmod +x xiaohongshu-mcp-darwin-arm64

# 直连启动（大多数情况）
./xiaohongshu-mcp-darwin-arm64 -port :18060

# 需要代理时（如公司内网、IP 池等特殊网络场景）
./xiaohongshu-mcp-darwin-arm64 -port :18060 -rod "proxy=http://127.0.0.1:7897"
```

### 3. 扫码登录

```bash
# 使用登录助手
./xiaohongshu-login-darwin-arm64
```

### 4. 发布第一条笔记

```bash
curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{
    "jsonrpc":"2.0","id":3,
    "method":"tools/call",
    "params":{
      "name":"publish_content",
      "arguments":{
        "title":"Hello from API 🚀",
        "content":"我的第一条自动化笔记！",
        "images":["/path/to/image.jpg"],
        "tags":["测试","自动化"]
      }
    }
  }'
```

## MCP 工具一览

| 工具 | 说明 |
|------|------|
| `check_login_status` | 检查登录状态 |
| `get_login_qrcode` | 获取登录二维码 |
| `publish_content` | 发布图文笔记 |
| `publish_with_video` | 发布视频笔记 |
| `search_feeds` | 搜索笔记 |
| `get_feed_detail` | 获取笔记详情+评论 |
| `post_comment_to_feed` | 发表评论 |
| `reply_comment_in_feed` | 回复评论 |
| `like_feed` | 点赞/取消点赞 |
| `favorite_feed` | 收藏/取消收藏 |
| `list_feeds` | 获取首页推荐 |
| `user_profile` | 获取用户主页 |
| `get_self_info` | 获取自己的信息 |

## CDP 数据脚本

MCP 不支持的功能用 Python CDP 脚本：

```bash
pip install -r requirements.txt

# 创作者数据看板
python scripts/cdp_publish.py content-data --csv-file output.csv

# 通知提及
python scripts/cdp_publish.py get-notification-mentions

# 高级搜索
python scripts/cdp_publish.py search-feeds --keyword "AI创业" --sort-by 最新
```

## 注意事项

- `check_login_status` 有 DOM 检测 bug，用 `search_feeds` 验证登录态
- 发布后返回空 PostID 是正常的，用搜索确认
- **不要重试发布** — 超时不代表失败
- 如有代理需求（公司内网、IP 池等），可加 `-rod "proxy=..."` 参数
- `visibility` 必须用中文值

## 许可证

[MIT](./LICENSE)

---

<p align="center">
  <sub>由 <a href="https://github.com/Youhai020616">Youhai</a> 用 ❤️ 构建</sub>
</p>
