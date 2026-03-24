@echo off
chcp 65001 >nul 2>&1
echo.
echo ╔═══════════════════════════════════╗
echo ║  📕 xhs-cli 一键安装 (Windows)   ║
echo ╚═══════════════════════════════════╝
echo.

:: 1. 检测 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo ✓ Python: %PYVER%

:: 2. 定位项目
set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%pyproject.toml" (
    echo ✗ 找不到 pyproject.toml
    pause
    exit /b 1
)
echo ✓ 项目目录: %PROJECT_DIR%

:: 3. 虚拟环境
set "VENV_DIR=%PROJECT_DIR%.venv"
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ℹ 创建虚拟环境...
    python -m venv "%VENV_DIR%"
)
call "%VENV_DIR%\Scripts\activate.bat"
echo ✓ 虚拟环境已激活

:: 4. 安装
echo ℹ 安装依赖...
pip install -e . --quiet
echo ✓ 依赖安装完成

:: 5. 验证
where xhs >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ xhs 命令可用
) else (
    echo ✗ xhs 命令安装失败
    pause
    exit /b 1
)

:: 6. MCP 二进制
if exist "%PROJECT_DIR%mcp\xiaohongshu-mcp-windows-amd64.exe" (
    echo ✓ MCP 二进制已就绪 (windows-amd64)
) else (
    echo ⚠ MCP 二进制不存在
    echo   运行 'xhs server install' 自动下载
)

echo.
echo ════════════════════════════════════
echo   ✅ 安装完成!
echo ════════════════════════════════════
echo.
echo   接下来:
echo     .venv\Scripts\activate
echo     xhs init
echo.
pause
