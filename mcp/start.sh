#!/bin/bash
# 启动小红书 MCP 服务 (跨平台)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 自动检测当前平台的二进制
case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)   BIN_NAME="xiaohongshu-mcp-darwin-arm64" ;;
    Darwin-x86_64)  BIN_NAME="xiaohongshu-mcp-darwin-amd64" ;;
    Linux-x86_64)   BIN_NAME="xiaohongshu-mcp-linux-amd64"  ;;
    Linux-aarch64)  BIN_NAME="xiaohongshu-mcp-linux-arm64"  ;;
    *)              echo "[mcp] 不支持的平台: $(uname -s)-$(uname -m)"; exit 1 ;;
esac

if [ ! -f "$SCRIPT_DIR/$BIN_NAME" ]; then
    echo "[mcp] 二进制不存在: $BIN_NAME"
    echo "[mcp] 请运行: xhs server install"
    exit 1
fi

# 检查是否已在运行
if pgrep -f "$BIN_NAME" > /dev/null; then
    echo "[mcp] Already running (PID $(pgrep -f "$BIN_NAME"))"
    exit 0
fi

# 启动（COOKIES_PATH 确保登录态持久化）
PORT="${MCP_PORT:-18060}"
echo "[mcp] Starting $BIN_NAME on port $PORT..."
export COOKIES_PATH="$SCRIPT_DIR/cookies.json"

# 代理通过 XHS_PROXY 环境变量传递 (Go 二进制不接受 -rod flag)
export XHS_PROXY="${XHS_PROXY:-}"

nohup "$SCRIPT_DIR/$BIN_NAME" -port ":$PORT" > mcp.log 2>&1 &
echo "[mcp] Started (PID $!)"
