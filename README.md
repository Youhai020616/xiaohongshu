<p align="center">
  <h1 align="center">📕 redbook-cli</h1>
  <p align="center">Xiaohongshu (小红书/RED) CLI — search, publish, engage, and analyze.</p>
</p>

<p align="center">
  <a href="https://pypi.org/project/redbook-cli/"><img src="https://img.shields.io/pypi/v/redbook-cli.svg" alt="PyPI"></a>
  <a href="https://github.com/Youhai020616/xiaohongshu/actions"><img src="https://github.com/Youhai020616/xiaohongshu/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/redbook-cli/"><img src="https://img.shields.io/badge/python-≥3.10-blue.svg" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

<p align="center">
  <a href="#install">Install</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#commands">Commands</a> •
  <a href="#features">Features</a> •
  <a href="./LICENSE">License</a>
</p>

---

<p align="center">
  <img src="./demo.gif" alt="redbook-cli demo" width="800">
</p>

## Install

```bash
pip install redbook-cli
```

Or from source:

```bash
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu && bash setup.sh
```

## Quick Start

```bash
xhs init                                 # Guided setup (first time)
xhs search "美食"                         # Search → results cached
xhs read 1                               # Read 1st result (short index)
xhs like 1                               # Like 1st result
xhs fav 2                                # Favorite 2nd result
xhs comment 1 -c "好文!"                  # Comment on 1st result
xhs publish -t "标题" -c "内容" -i img.jpg  # Publish image post
```

## Features

- 🔍 **Search** — keyword search with sort/type/time filters, export to CSV/JSON
- 📝 **Publish** — image & video posts with tags, scheduling, visibility control
- 💬 **Interact** — like, favorite, comment, reply (short index support)
- 📊 **Analytics** — creator dashboard data export (CDP)
- 🔔 **Notifications** — mentions and interaction notifications
- 👤 **Profile** — user info and post listing
- 🔢 **Short Index** — `xhs search → xhs read 1 → xhs like 1`
- 📦 **Export** — `xhs search "AI" -o results.csv`
- 🔐 **Login** — MCP QR scan + CDP browser login
- 👥 **Multi-Account** — isolated Chrome profiles per account
- 🏗️ **Dual Engine** — MCP server (fast) + CDP scripts (full features)

## Commands

### Search & Read

```bash
xhs search "关键词"                        # Basic search
xhs search "旅行" --sort 最多点赞          # Sort by likes
xhs search "穿搭" --type 图文             # Filter by type
xhs search "AI" -o results.csv           # Export to CSV
xhs read 1                               # Read by short index
xhs detail FEED_ID -t TOKEN              # Read by ID + token
```

### Publish

```bash
xhs publish -t "标题" -c "正文" -i photo.jpg                       # Image post
xhs publish -t "标题" -c "正文" -v video.mp4                       # Video post
xhs publish -t "标题" -c "正文" -i img.jpg --tags 旅行 --tags 美食  # With tags
xhs publish -t "测试" -c "内容" -i img.jpg --visibility 仅自己可见   # Private
xhs pub -t "标题" -c "正文" -i img.jpg --dry-run                    # Preview
```

### Interact

```bash
xhs like 1                               # Like (short index)
xhs like FEED_ID -t TOKEN --unlike       # Unlike
xhs fav 1                                # Favorite
xhs comment 1 -c "写得好!"               # Comment
xhs reply 1 --comment-id X --user-id Y -c "回复"  # Reply
```

### Analytics & Feed

```bash
xhs analytics                            # Creator dashboard
xhs analytics --csv data.csv             # Export CSV
xhs notifications                        # Messages
xhs feeds                                # Recommendation feed
```

### Profile

```bash
xhs me                                   # My info
xhs profile USER_ID -t TOKEN             # User profile
```

### Account & Config

```bash
xhs login                                # MCP QR scan
xhs login --cdp                          # CDP browser login
xhs status                               # Login status
xhs server start                         # Start MCP server
xhs server stop                          # Stop MCP server
xhs account list                         # List accounts
xhs config show                          # Show config
xhs config set mcp.proxy http://...      # Set proxy
```

### Aliases

| Short | Command | | Short | Command |
|-------|---------|---|-------|---------|
| `xhs s` | `search` | | `xhs r` | `detail` (read) |
| `xhs pub` | `publish` | | `xhs fav` | `favorite` |
| `xhs cfg` | `config` | | `xhs acc` | `account` |
| `xhs srv` | `server` | | `xhs noti` | `notifications` |

## Architecture

| Engine | Used for | Technology |
|--------|----------|------------|
| **MCP Server** | Publish, search, like, comment, profile | Go binary, JSON-RPC |
| **CDP Scripts** | Analytics, notifications, advanced search | Python, Chrome DevTools |

MCP is the primary engine (always-on daemon). CDP is used for features MCP doesn't support.

**Unique features** (vs competitors): video publish, scheduled publish, visibility control, analytics dashboard, multi-account isolation.

## Platform Support

| Component | macOS ARM64 | macOS x86 | Linux | Windows |
|-----------|:-----------:|:---------:|:-----:|:-------:|
| **xhs CLI** | ✅ | ✅ | ✅ | ✅ |
| MCP Server | ✅ | ❌ | ❌ | ❌ |
| CDP Scripts | ✅ | ✅ | ✅ | ✅ |

**Non-ARM64 users**: `xhs init` auto-detects missing MCP and switches to CDP-only mode.

## License

[MIT](./LICENSE)

## 🔗 Ecosystem

| Project | Description |
|---------|-------------|
| [AgentMind](https://github.com/Youhai020616/Agentmind) | Self-learning memory system for AI agents |
| [stealth-cli](https://github.com/Youhai020616/stealth-cli) | Anti-detection browser CLI powered by Camoufox |
| [stealth-x](https://github.com/Youhai020616/stealth-x) | Stealth X/Twitter automation |
| [dy-cli](https://github.com/Youhai020616/douyin) | Douyin/TikTok CLI |
| [freepost](https://github.com/Youhai020616/freepost-saas) | AI social media management |
