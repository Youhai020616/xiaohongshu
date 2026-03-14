#!/usr/bin/env bash
# 激活 xhs-cli 环境
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/Scripts/activate" ]; then
    source "$SCRIPT_DIR/.venv/Scripts/activate"
else
    source "$SCRIPT_DIR/.venv/bin/activate"
fi
echo "📕 xhs-cli 环境已激活，输入 xhs --help 开始使用"
