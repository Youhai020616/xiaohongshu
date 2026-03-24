# ---- redbook-cli Docker Image ----
# 基于上游 xiaohongshu-mcp Docker 镜像，叠加 Python CLI + CDP 能力
#
# 使用方式:
#   docker compose up -d          # 启动
#   docker compose exec cli xhs search "关键词"  # 使用 CLI

FROM xpzouying/xiaohongshu-mcp AS mcp-base

# ---- Python CLI + CDP 层 ----
FROM python:3.11-slim

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 安装 Chrome (CDP 脚本需要) + 中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    fonts-noto-cjk \
    procps \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 从上游镜像复制 MCP 二进制
COPY --from=mcp-base /app/app /app/mcp/xiaohongshu-mcp-linux-amd64
RUN chmod +x /app/mcp/xiaohongshu-mcp-linux-amd64

# 安装 Python 依赖
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir click rich requests websockets PyYAML

# 复制项目文件
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/ ./config/

# 安装 CLI
RUN pip install --no-cache-dir -e .

# 创建数据目录
RUN mkdir -p /app/data/cookies /app/data/images /root/.xhs

# 环境变量
ENV ROD_BROWSER_BIN=/usr/bin/google-chrome
ENV COOKIES_PATH=/app/data/cookies/cookies.json
ENV PYTHONUNBUFFERED=1

EXPOSE 18060 9222

# 默认启动 MCP 服务
CMD ["/app/mcp/xiaohongshu-mcp-linux-amd64"]
