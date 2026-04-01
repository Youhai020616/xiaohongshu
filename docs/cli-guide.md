# 📕 xhs-cli 使用指南

小红书命令行工具 — 一条命令搞定发布、搜索、互动、数据分析。

## 安装

### 前提条件

- macOS Apple Silicon (M1/M2/M3/M4) — MCP 引擎需要
- Python 3.9+
- Google Chrome — CDP 功能需要 (数据看板、通知等)

### 一键安装 (推荐)

```bash
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu
bash setup.sh
```

`setup.sh` 会自动完成:
- ✅ 检测 Python 版本
- ✅ 创建虚拟环境 `.venv`
- ✅ 安装所有依赖 (`click`, `rich`, `requests`, `websockets`)
- ✅ 注册 `xhs` 命令
- ✅ 检查 MCP 二进制
- ✅ 生成 `activate.sh` 快捷激活脚本

### 手动安装

```bash
git clone https://github.com/Youhai020616/xiaohongshu.git
cd xiaohongshu
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
xhs --version
```

## 快速开始

### 首次使用: 初始化

```bash
source activate.sh    # 激活环境
xhs init              # 引导式初始化
```

`xhs init` 会自动引导你完成:
1. ✅ 检查系统环境 (MCP 二进制、Chrome、Python)
2. ✅ 配置网络代理 (可选，无需代理直接回车跳过)
3. ✅ 启动 MCP 服务
4. ✅ 扫码登录小红书

### 以后每次使用

```bash
source activate.sh    # 激活环境 (MCP 服务会在后台持续运行)
xhs search "关键词"   # 直接用
```

### 手动管理

```bash
xhs server start                        # 启动 MCP
xhs server start --no-proxy             # 不使用代理直连
xhs server start --proxy http://...     # 指定代理
xhs login                               # 登录
xhs status                              # 检查状态
```

---

## 常用命令速查

### 发布

```bash
# 图文发布
xhs publish -t "标题" -c "正文内容" -i photo1.jpg -i photo2.jpg

# 带标签
xhs publish -t "旅行日记" -c "巴厘岛真美" -i bali.jpg --tags 旅行 --tags 巴厘岛

# 视频发布
xhs publish -t "Vlog" -c "日常" -v video.mp4

# 仅自己可见 (测试用)
xhs publish -t "测试" -c "测试内容" -i test.jpg --visibility 仅自己可见

# 定时发布
xhs publish -t "早安" -c "新的一天" -i sunrise.jpg --schedule "2026-03-16T08:00:00+08:00"

# 预览不发布
xhs publish -t "标题" -c "正文" -i photo.jpg --dry-run

# 从文件读取长文
xhs publish -t "深度文章" --content-file article.txt -i cover.jpg
```

### 搜索

```bash
# 基础搜索
xhs search "AI创业"

# 筛选排序
xhs search "春招" --sort 最新
xhs search "咖啡" --sort 最多点赞 --type 图文

# 限制时间
xhs search "热点" --time 一天内

# 使用 CDP 引擎 (返回推荐关键词)
xhs search "摄影" --engine cdp

# 输出 JSON (适合程序处理)
xhs search "科技" --json-output
```

### 互动

```bash
# 点赞
xhs like FEED_ID -t XSEC_TOKEN

# 取消点赞
xhs like FEED_ID -t XSEC_TOKEN --unlike

# 收藏
xhs favorite FEED_ID -t XSEC_TOKEN

# 评论
xhs comment FEED_ID -t XSEC_TOKEN -c "写得好!"
```

> 💡 **FEED_ID 和 TOKEN 从哪来?**
> 搜索结果中会包含 `feed_id` 和 `xsec_token`，使用 `--json-output` 查看完整数据。

### 笔记详情

```bash
# 查看详情
xhs detail FEED_ID -t XSEC_TOKEN

# 包含评论
xhs detail FEED_ID -t XSEC_TOKEN --comments

# JSON 输出
xhs detail FEED_ID -t XSEC_TOKEN --json-output
```

### 个人信息

```bash
# 查看自己的信息
xhs me

# 查看别人的主页
xhs profile USER_ID -t XSEC_TOKEN
```

### 数据看板 (CDP)

```bash
# 查看创作数据
xhs analytics

# 导出 CSV
xhs analytics --csv data.csv

# 查看通知
xhs notifications
```

### 首页推荐

```bash
xhs feeds
```

---

## 服务管理

```bash
xhs server start              # 启动
xhs server stop               # 停止
xhs server status             # 状态
xhs server log                # 查看日志
xhs server log -n 100         # 最后 100 行日志
```

## 多账号

```bash
xhs account list               # 列出账号
xhs account add work -a "工作号"  # 添加
xhs login --cdp --account work  # 登录
xhs account default work        # 设为默认
xhs account remove work         # 删除
```

## 配置

配置文件位于 `~/.xhs/config.json`:

```bash
xhs config show                # 查看配置
xhs config set mcp.proxy http://127.0.0.1:7897  # 设置代理
xhs config set mcp.port 18060  # 设置端口
xhs config set default.engine mcp  # 默认引擎
xhs config reset               # 重置默认
```

---

## 命令别名

输入更快:

| 别名 | 完整命令 |
|------|---------|
| `xhs pub` | `xhs publish` |
| `xhs s` | `xhs search` |
| `xhs fav` | `xhs favorite` |
| `xhs noti` | `xhs notifications` |
| `xhs stat` | `xhs status` |
| `xhs srv` | `xhs server` |
| `xhs acc` | `xhs account` |
| `xhs cfg` | `xhs config` |

---

## 引擎说明

| 引擎 | 优势 | 劣势 |
|------|------|------|
| **MCP** | 快速(常驻)、零依赖 | 不支持数据看板/通知 |
| **CDP** | 数据看板、推荐词、通知 | 需要 Chrome、较慢 |

大多数命令默认 `--engine auto`:
- MCP 服务在运行 → 用 MCP
- MCP 未运行 → 自动降级到 CDP

只有 `analytics` 和 `notifications` 固定使用 CDP（MCP 不支持这些功能）。

---

## 常见问题

### Q: 提示"MCP 服务未运行"?
```bash
xhs server start
```

### Q: 访问超时?
如果你的网络环境需要代理（如公司内网、特殊网络等），可配置代理：
```bash
xhs config set mcp.proxy http://127.0.0.1:7897
xhs server stop
xhs server start
```

### Q: 发布后 PostID 为空?
这是正常行为，用搜索验证:
```bash
xhs search "你的标题"
```

### Q: 如何不使用代理直连?
```bash
xhs server start --no-proxy
```
