---
name: xiaohongshu
description: |
  小红书全能 Skill：发布图文/视频、搜索笔记、评论互动、数据看板、通知抓取、推荐词。
  MCP 负责发布和互动（常驻），RedBookSkills CDP 负责数据分析和监控（按需启动）。
metadata:
  trigger: 小红书相关操作（发布、搜索、评论、数据、通知）
---

# 小红书统一 Skill

本 Skill 整合两套工具：
- **MCP**（Go 二进制）：发布、搜索、评论、点赞、收藏 — 常驻后台，零启动
- **CDP Scripts**（Python）：数据看板、通知抓取、搜索推荐词 — 按需启动 Chrome

## 目录结构

```
xiaohongshu/
├── SKILL.md
├── mcp/
│   ├── xiaohongshu-mcp-darwin-arm64
│   ├── xiaohongshu-login-darwin-arm64
│   └── cookies.json
├── scripts/
│   ├── cdp_publish.py
│   ├── chrome_launcher.py
│   ├── feed_explorer.py
│   ├── publish_pipeline.py
│   ├── account_manager.py
│   ├── image_downloader.py
│   └── run_lock.py
├── config/
│   └── accounts.json.example
├── requirements.txt
└── LICENSE
```

## 工具选择指南

| 操作 | 用哪个 | 原因 |
|------|--------|------|
| 发布图文/视频 | MCP | 29s 完成，零依赖 |
| 搜索笔记 | MCP | 常驻，响应快 |
| 评论/回复 | MCP | 稳定 |
| 点赞/收藏/关注 | MCP | 稳定 |
| 用户主页 | MCP | 稳定 |
| **数据看板** | CDP | MCP 不支持 |
| **通知抓取** | CDP | MCP 不支持 |
| **搜索推荐词** | CDP | MCP 不支持 |
| 笔记详情 | CDP | 更丰富的字段 |

---

## Part 1: MCP 工具（发布/互动）

### 启动 MCP 服务

```bash
cd {SKILL_DIR}/mcp
# 直连启动（大多数情况）
./xiaohongshu-mcp-darwin-arm64 -port :18060

# 如需代理（公司内网、IP 池等特殊场景）
# ./xiaohongshu-mcp-darwin-arm64 -port :18060 -rod "proxy=http://127.0.0.1:7897"
```

### MCP 协议调用

MCP 使用 JSON-RPC over HTTP（端口 18060）。调用流程：

```bash
# 1. 初始化 session
curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"openclaw","version":"1.0"}}}' \
  -D -

# 从响应头拿 Mcp-Session-Id

# 2. 发送 initialized 通知
curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. 调用工具
curl -s -X POST http://127.0.0.1:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"TOOL_NAME","arguments":{...}}}'
```

### MCP 可用工具（17个）

| 工具名 | 参数 | 说明 |
|--------|------|------|
| check_login_status | — | 检查登录状态（有 bug，建议用 search_feeds 验证） |
| get_login_qrcode | — | 获取登录二维码（Base64 图片） |
| delete_cookies | — | 删除 cookies，重置登录态 |
| publish_content | title, content, images, tags?, visibility?, is_original?, schedule_at? | 发布图文 |
| **publish_with_video** | **title, content, video, tags?, visibility?, schedule_at?** | **发布视频（本地绝对路径）** |
| search_feeds | keyword, filters? | 搜索笔记 |
| get_feed_detail | feed_id, xsec_token, load_all_comments?, limit? | 获取笔记详情+评论 |
| post_comment_to_feed | feed_id, xsec_token, content | 评论笔记 |
| reply_comment_in_feed | feed_id, xsec_token, comment_id, user_id, content | 回复评论 |
| like_feed | feed_id, xsec_token, unlike? | 点赞/取消点赞 |
| favorite_feed | feed_id, xsec_token, unfavorite? | 收藏/取消收藏 |
| list_feeds | — | 获取首页 Feeds 列表 |
| user_profile | user_id, xsec_token | 获取用户主页+笔记 |
| get_self_info | — | 获取自己的信息 |

> ⚠️ **注意**：视频发布工具名是 `publish_with_video`（不是 `publish_video`），video 参数传本地绝对路径

### MCP 注意事项
- cookies 在 `{SKILL_DIR}/mcp/cookies.json`
- 代理为可选配置，大多数网络环境可直连。如需代理：`-rod "proxy=http://127.0.0.1:7897"`
- PostID 返回空是正常行为，用 search_feeds 搜昵称验证
- reply_comment_in_feed 有 bug，用 post_comment_to_feed 替代
- 同一账号不能多端网页登录（会踢 MCP session）
- check_login_status 有 DOM 检测 bug，用 search_feeds 验证登录态
- visibility 必须用中文值：`公开可见`、`仅自己可见`、`仅互关好友可见`
- publish_content 的 images 支持文件路径和 HTTP URL（路径更快，避免超时）
- publish_with_video 的 video 只接受本地绝对路径
- schedule_at 格式：ISO8601 如 `2024-01-20T10:30:00+08:00`

---

## Part 2: CDP Scripts（数据/分析）

### 前置条件

```bash
pip install -r {SKILL_DIR}/requirements.txt
```

Chrome 使用独立 Profile：`~/Google/Chrome/XiaohongshuProfiles/default/`

### 启动/关闭 Chrome

```bash
python3 {SKILL_DIR}/scripts/chrome_launcher.py            # 有窗口
python3 {SKILL_DIR}/scripts/chrome_launcher.py --headless  # 无头
python3 {SKILL_DIR}/scripts/chrome_launcher.py --kill      # 关闭
```

### 登录

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py login        # 首次扫码
python3 {SKILL_DIR}/scripts/cdp_publish.py check-login   # 检查（12h缓存）
```

### 数据看板 ⭐（MCP 不支持）

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py content-data
python3 {SKILL_DIR}/scripts/cdp_publish.py --reuse-existing-tab content-data --csv-file "/path/output.csv"
```

### 通知抓取 ⭐（MCP 不支持）

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py get-notification-mentions
```

### 搜索 + 推荐词 ⭐（MCP 不支持）

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py search-feeds --keyword "AI创业"
python3 {SKILL_DIR}/scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新 --note-type 图文
```

### 笔记详情

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py get-feed-detail --feed-id FEED_ID --xsec-token XSEC_TOKEN
```

### 发表评论

```bash
python3 {SKILL_DIR}/scripts/cdp_publish.py post-comment-to-feed --feed-id FEED_ID --xsec-token XSEC_TOKEN --content "写得很实用"
```

### CDP 图文发布（备用）

```bash
python3 {SKILL_DIR}/scripts/publish_pipeline.py --headless \
  --title-file title.txt --content-file content.txt --image-urls "URL1" "URL2"
```

### CDP 参数顺序

全局参数在子命令前，子命令参数在子命令后：
```bash
python3 scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新
```

---

## Part 3: 运维指南

### 登录态维护
- MCP cookies：常驻，很少过期
- CDP 登录：缓存 12h，过期需重新启动 Chrome 检查
- 两套登录态互相独立，互不影响

### 账号信息
- 账号：AI出海工具人
- userid：66f7633c000000001d032384

### 发帖规范
- 标题 ≤ 20 字，正文 ≤ 1000 字
- 图文流量 > 视频 > 纯文字
- 每天上限 50 篇
- 新号别勾选"声明原创"
- 不提外部平台名，文案口语化

### 失败处理
- MCP 无响应：检查进程 `ps aux | grep xiaohongshu-mcp`，重启服务即可
- CDP 登录过期：`chrome_launcher.py` 启动 → `cdp_publish.py login` 扫码
- "Execution context was destroyed"：正常警告，不影响数据


