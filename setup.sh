#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#  📕 xhs-cli 一键安装脚本
#  用法: curl -sSL <url> | bash   或   bash setup.sh
# ═══════════════════════════════════════════════════════
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
fail()    { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo -e "${BOLD}╔═══════════════════════════════════╗${NC}"
echo -e "${BOLD}║  📕 xhs-cli 一键安装             ║${NC}"
echo -e "${BOLD}║  小红书命令行工具                 ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════╝${NC}"
echo ""

# ── 1. 检测 Python ──────────────────────────────────
info "检查 Python..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "需要 Python 3.9+，请先安装: brew install python3"
fi
success "Python: $($PYTHON --version)"

# ── 2. 定位项目目录 ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
else
    PROJECT_DIR="$(pwd)"
fi

if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
    fail "找不到 pyproject.toml，请在项目根目录运行此脚本"
fi
cd "$PROJECT_DIR"
success "项目目录: $PROJECT_DIR"

# ── 3. 创建虚拟环境 ──────────────────────────────────
VENV_DIR="$PROJECT_DIR/.venv"
if [ -d "$VENV_DIR" ] && { [ -f "$VENV_DIR/bin/activate" ] || [ -f "$VENV_DIR/Scripts/activate" ]; }; then
    success "虚拟环境已存在: $VENV_DIR"
else
    info "创建虚拟环境..."
    $PYTHON -m venv "$VENV_DIR"
    success "虚拟环境已创建"
fi

# ── 4. 安装依赖 ──────────────────────────────────────
info "安装依赖..."
if [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi
pip install -e . --quiet 2>&1 | tail -1
success "依赖安装完成"

# ── 5. 验证 xhs 命令 ────────────────────────────────
if command -v xhs &>/dev/null; then
    success "xhs 命令可用: $(xhs --version 2>&1)"
else
    fail "xhs 命令安装失败"
fi

# ── 6. MCP 二进制检查 ────────────────────────────────
MCP_BIN="$PROJECT_DIR/mcp/xiaohongshu-mcp-darwin-arm64"
if [ -f "$MCP_BIN" ]; then
    chmod +x "$MCP_BIN"
    chmod +x "$PROJECT_DIR/mcp/xiaohongshu-login-darwin-arm64" 2>/dev/null || true
    success "MCP 二进制已就绪"
else
    warn "MCP 二进制不存在 (仅 macOS ARM64 支持)"
fi

# ── 7. 生成激活脚本 ──────────────────────────────────
ACTIVATE_SCRIPT="$PROJECT_DIR/activate.sh"
cat > "$ACTIVATE_SCRIPT" << 'EOF'
#!/usr/bin/env bash
# 激活 xhs-cli 环境
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/Scripts/activate" ]; then
    source "$SCRIPT_DIR/.venv/Scripts/activate"
else
    source "$SCRIPT_DIR/.venv/bin/activate"
fi
echo "📕 xhs-cli 环境已激活，输入 xhs --help 开始使用"
EOF
chmod +x "$ACTIVATE_SCRIPT"

# ── 完成 ─────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 安装完成!${NC}"
echo -e "${GREEN}════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}接下来:${NC}"
echo ""
echo -e "  ${CYAN}# 方式一: 直接初始化 (推荐)${NC}"
echo -e "  source activate.sh && xhs init"
echo ""
echo -e "  ${CYAN}# 方式二: 手动激活环境后使用${NC}"
echo -e "  source .venv/bin/activate"
echo -e "  xhs init"
echo ""
echo -e "  ${CYAN}# 以后每次使用前激活环境:${NC}"
echo -e "  source activate.sh"
echo ""
