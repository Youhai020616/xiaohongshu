<p align="center">
  <h1 align="center">📕 xiaohongshu</h1>
  <p align="center">AI-powered Xiaohongshu (小红书/RED) automation — publish, search, engage, and analyze.</p>
</p>

<p align="center">
  <a href="#cli-quick-start">CLI Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#mcp-tools">MCP Tools</a> •
  <a href="#cdp-scripts">CDP Scripts</a> •
  <a href="#openclaw-integration">OpenClaw</a> •
  <a href="#claude-code-integration">Claude Code</a> •
  <a href="./LICENSE">License</a>
</p>

---

<p align="center">
  <img src="./demo.gif" alt="xiaohongshu demo" width="800">
</p>

## CLI Quick Start

The fastest way to get started — **3 commands** from zero to posting:

```bash
# 1. Clone
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu

# 2. One-click install (auto: Python check → venv → pip install → MCP binary)
bash setup.sh

# 3. Initialize (auto: proxy config → start MCP → QR login)
source activate.sh && xhs init
```

Then just use:

```bash
xhs search "AI创业"                                          # Search
xhs publish -t "Hello" -c "My first post" -i photo.jpg      # Publish
xhs like FEED_ID -t TOKEN                                    # Like
xhs analytics                                                # Dashboard
xhs --help                                                   # All commands
```

> 📖 Full CLI guide: [docs/cli-guide.md](docs/cli-guide.md)

---

## What is this?

A complete toolkit for automating Xiaohongshu (小红书/RED Note) operations through two complementary engines:

| Engine | Technology | Use Cases | Startup |
|--------|-----------|-----------|---------|
| **MCP Server** | Go binary, JSON-RPC | Publish, search, comment, like, follow | Always-on daemon |
| **CDP Scripts** | Python, Chrome DevTools | Analytics dashboard, notifications, advanced search | On-demand |

Built as an [OpenClaw](https://github.com/openclaw/openclaw) Skill, but works standalone or with any MCP-compatible client (Claude Code, Cursor, etc.).

## Features

- 📝 **Publish** — Image posts and video posts with tags, scheduling, and visibility control
- 🔍 **Search** — Keyword search with filters (sort, note type, suggested keywords)
- 💬 **Engage** — Comment, reply, like, favorite on any post
- 👤 **Profile** — Fetch any user's profile and posts
- 📊 **Analytics** — Creator dashboard data export (CSV), content performance metrics
- 🔔 **Notifications** — Fetch mentions and interaction notifications
- 👥 **Multi-Account** — Isolated Chrome profiles per account
- 🔐 **QR Code Login** — Scan-to-login, persistent cookie storage

## Quick Start

### Prerequisites

- macOS (Apple Silicon) — MCP binary is pre-built for `darwin-arm64`
- Python 3.9+ (for CDP scripts)
- Google Chrome (for CDP scripts and QR login)
- A proxy/VPN if outside China (MCP requires `-rod` proxy flag)

### 1. Clone

```bash
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu
```

### 2. Start MCP Server

```bash
cd mcp
chmod +x xiaohongshu-mcp-darwin-arm64

# Without proxy (inside China)
./xiaohongshu-mcp-darwin-arm64 -port :18060

# With proxy (outside China)
./xiaohongshu-mcp-darwin-arm64 -port :18060 -rod "proxy=http://127.0.0.1:7897"
```

### 3. Login

On first run, get a QR code to scan with your Xiaohongshu app:

```bash
curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cli","version":"1.0"}}}'
# Save the Mcp-Session-Id from response headers

curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_login_qrcode","arguments":{}}}'
```

Or use the login helper binary:

```bash
cd mcp
./xiaohongshu-login-darwin-arm64
```

### 4. Publish Your First Post

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
        "content":"My first automated post on Xiaohongshu!",
        "images":["/path/to/image.jpg"],
        "tags":["测试","自动化"]
      }
    }
  }'
```

## MCP Tools

The MCP server exposes these tools via the [Model Context Protocol](https://modelcontextprotocol.io/):

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `check_login_status` | Check if logged in | — |
| `get_login_qrcode` | Get QR code for login (base64) | — |
| `delete_cookies` | Reset login state | — |
| `publish_content` | Publish image post | `title`, `content`, `images`, `tags?`, `visibility?`, `is_original?`, `schedule_at?` |
| `publish_with_video` | Publish video post | `title`, `content`, `video` (local path), `tags?`, `visibility?`, `schedule_at?` |
| `search_feeds` | Search posts by keyword | `keyword`, `filters?` |
| `get_feed_detail` | Get post details + comments | `feed_id`, `xsec_token`, `load_all_comments?` |
| `post_comment_to_feed` | Comment on a post | `feed_id`, `xsec_token`, `content` |
| `reply_comment_in_feed` | Reply to a comment | `feed_id`, `xsec_token`, `comment_id`, `user_id`, `content` |
| `like_feed` | Like / unlike a post | `feed_id`, `xsec_token`, `unlike?` |
| `favorite_feed` | Favorite / unfavorite a post | `feed_id`, `xsec_token`, `unfavorite?` |
| `list_feeds` | Get homepage feed | — |
| `user_profile` | Get user profile + posts | `user_id`, `xsec_token` |
| `get_self_info` | Get own account info | — |

### MCP Session Protocol

The MCP server uses [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http) transport. Every request must include:

```
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: <from initialize response header>
```

Session lifecycle: `initialize` → `notifications/initialized` → `tools/call` (repeat)

### Parameters Reference

**`publish_content`**
- `title` (string, required) — Max 20 Chinese characters
- `content` (string, required) — Post body, max 1000 characters. Do NOT include hashtags here
- `images` (string[], required) — Local file paths or HTTP URLs (at least 1)
- `tags` (string[], optional) — Hashtags, e.g. `["旅行", "美食"]`
- `visibility` (string, optional) — `公开可见` (default) / `仅自己可见` / `仅互关好友可见`
- `is_original` (bool, optional) — Declare as original content
- `schedule_at` (string, optional) — ISO 8601 datetime, e.g. `2026-03-15T10:30:00+08:00`

**`publish_with_video`**
- `video` (string, required) — Local absolute path to video file only

## CDP Scripts

For features the MCP server doesn't support (analytics, notifications, suggested keywords), use the Python CDP scripts:

### Setup

```bash
pip install -r requirements.txt
```

### Chrome Launcher

```bash
# Start Chrome with isolated profile
python scripts/chrome_launcher.py

# Headless mode
python scripts/chrome_launcher.py --headless

# Stop Chrome
python scripts/chrome_launcher.py --kill
```

### Available Commands

```bash
# Login (scan QR code)
python scripts/cdp_publish.py login

# Creator dashboard data → CSV
python scripts/cdp_publish.py content-data --csv-file output.csv

# Notification mentions
python scripts/cdp_publish.py get-notification-mentions

# Search with filters
python scripts/cdp_publish.py search-feeds --keyword "AI创业" --sort-by 最新 --note-type 图文

# Post detail
python scripts/cdp_publish.py get-feed-detail --feed-id FEED_ID --xsec-token TOKEN

# Comment
python scripts/cdp_publish.py post-comment-to-feed --feed-id FEED_ID --xsec-token TOKEN --content "Great post!"

# Publish via CDP (alternative to MCP)
python scripts/publish_pipeline.py --headless \
  --title-file title.txt --content-file content.txt \
  --image-urls "https://example.com/img.jpg"
```

### Multi-Account

```bash
python scripts/cdp_publish.py add-account work --alias "Work Account"
python scripts/cdp_publish.py --account work login
python scripts/cdp_publish.py --account work content-data
python scripts/cdp_publish.py list-accounts
```

## OpenClaw Integration

Install as an OpenClaw skill:

```bash
# Copy to skills directory
cp -r xiaohongshu ~/.openclaw/skills/xiaohongshu

# Start MCP server
cd ~/.openclaw/skills/xiaohongshu/mcp
./start.sh
```

The `SKILL.md` file provides full instructions for OpenClaw's AI agent to use the tools automatically.

## Claude Code Integration

See [docs/claude-code-integration.md](docs/claude-code-integration.md) for setup instructions with Claude Code.

## Tips & Known Issues

- **Login verification**: `check_login_status` has a DOM detection bug — use `search_feeds` with any keyword to verify login state
- **Post ID**: `publish_content` may return an empty PostID — this is normal. Use `search_feeds` with your username to verify
- **Don't retry publishing** — A timeout doesn't mean failure. Always verify before retrying
- **Proxy required**: Outside China, the MCP server needs `-rod "proxy=..."` flag
- **Concurrent sessions**: Don't log in to the same account from both MCP and web browser simultaneously
- **`visibility` values**: Must be in Chinese: `公开可见`, `仅自己可见`, `仅互关好友可见`
- **`schedule_at` range**: Must be between 1 hour and 14 days from now

## Platform Support

| Component | macOS ARM64 | macOS x86 | Linux | Windows |
|-----------|:-----------:|:---------:|:-----:|:-------:|
| **xhs CLI** | ✅ | ✅ | ✅ | ✅ |
| MCP Server | ✅ | ❌ | ❌ | ❌ |
| CDP Scripts | ✅ | ✅ | ✅ | ✅ |

**Windows / Linux / macOS x86 users**: Run `xhs init` — the CLI auto-detects missing MCP binary and switches to **CDP-only mode**. All features (publish, search, analytics, etc.) work through Chrome.

```bash
# Windows
setup.bat                    # One-click install
activate.bat && xhs init    # Initialize (auto CDP mode)

# macOS / Linux
bash setup.sh
source activate.sh && xhs init
```

## Project Structure

```
xiaohongshu/
├── README.md                          # This file
├── SKILL.md                           # OpenClaw skill definition
├── pyproject.toml                     # CLI package config (pip install -e .)
├── manifest.json                      # Skill metadata
├── LICENSE                            # MIT License
├── requirements.txt                   # Python dependencies (legacy)
├── .gitignore
├── src/xhs_cli/                       # ⭐ CLI package
│   ├── main.py                        # Unified entry point (xhs command)
│   ├── engines/
│   │   ├── mcp_client.py             # MCP JSON-RPC client (auto session)
│   │   └── cdp_client.py             # CDP scripts wrapper
│   ├── commands/
│   │   ├── init.py                   # xhs init (guided setup)
│   │   ├── auth.py                   # xhs login/logout/status
│   │   ├── publish.py                # xhs publish (auto engine)
│   │   ├── search.py                 # xhs search/detail
│   │   ├── interact.py               # xhs like/comment/favorite
│   │   ├── analytics.py              # xhs analytics/notifications
│   │   ├── account.py                # xhs account management
│   │   ├── profile.py                # xhs me/profile
│   │   ├── server.py                 # xhs server start/stop/status
│   │   └── config_cmd.py             # xhs config show/set/get
│   └── utils/
│       ├── config.py                  # ~/.xhs/config.json management
│       └── output.py                  # Rich formatted output
├── mcp/
│   ├── xiaohongshu-mcp-darwin-arm64   # MCP server binary
│   ├── xiaohongshu-login-darwin-arm64 # Login helper binary
│   └── start.sh                       # Startup script
├── scripts/
│   ├── cdp_publish.py                 # Main CDP automation (2700 lines)
│   ├── chrome_launcher.py             # Chrome lifecycle management
│   ├── publish_pipeline.py            # High-level publish workflow
│   ├── feed_explorer.py               # Feed browsing utilities
│   ├── account_manager.py             # Multi-account management
│   ├── image_downloader.py            # Image download helper
│   └── run_lock.py                    # Process locking
├── config/
│   └── accounts.json.example          # Account config template
└── docs/
    ├── cli-guide.md                   # ⭐ CLI usage guide
    └── claude-code-integration.md     # Claude Code setup guide
```

## Contributing

Issues and PRs welcome! Areas where help is needed:

- [ ] Cross-platform MCP builds (Linux, Windows, macOS x86)
- [ ] MCP Go source code release
- [ ] Video upload improvements
- [ ] Rate limiting and retry logic
- [ ] Test suite

## License

[MIT](./LICENSE)

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Youhai020616">Youhai</a></sub>
</p>
