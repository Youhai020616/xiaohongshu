@echo off
chcp 65001 >nul 2>&1
echo.
echo ╔═══════════════════════════════════╗
echo ║  📕 xhs-cli 一键安装             ║
echo ║  小红书命令行工具 (Windows)       ║
echo ╚═══════════════════════════════════╝
echo.

:: ── 1. 检测 Python ──────────────────────────────────
echo [*] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [X] 需要 Python 3.9+，请先安装: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)
for /f "tokens=*" %%i in ('%PYTHON% --version 2^>^&1') do echo [OK] %%i

:: ── 2. 定位项目目录 ──────────────────────────────────
set PROJECT_DIR=%~dp0
if not exist "%PROJECT_DIR%pyproject.toml" (
    echo [X] 找不到 pyproject.toml，请在项目根目录运行此脚本
    pause
    exit /b 1
)
echo [OK] 项目目录: %PROJECT_DIR%

:: ── 3. 创建虚拟环境 ──────────────────────────────────
if exist "%PROJECT_DIR%.venv\Scripts\activate.bat" (
    echo [OK] 虚拟环境已存在
) else (
    echo [*] 创建虚拟环境...
    %PYTHON% -m venv "%PROJECT_DIR%.venv"
    echo [OK] 虚拟环境已创建
)

:: ── 4. 安装依赖 ──────────────────────────────────────
echo [*] 安装依赖...
call "%PROJECT_DIR%.venv\Scripts\activate.bat"
pip install -e "%PROJECT_DIR%." --quiet 2>&1 | findstr /V "notice"
echo [OK] 依赖安装完成

:: ── 5. 验证 xhs 命令 ────────────────────────────────
xhs --version >nul 2>&1
if errorlevel 1 (
    echo [X] xhs 命令安装失败
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('xhs --version 2^>^&1') do echo [OK] xhs 命令可用: %%i

:: ── 6. 生成激活脚本 ──────────────────────────────────
(
echo @echo off
echo call "%PROJECT_DIR%.venv\Scripts\activate.bat"
echo echo 📕 xhs-cli 环境已激活，输入 xhs --help 开始使用
) > "%PROJECT_DIR%activate.bat"

:: ── 完成 ─────────────────────────────────────────────
echo.
echo ════════════════════════════════════
echo   [OK] 安装完成!
echo ════════════════════════════════════
echo.
echo   接下来:
echo.
echo   :: 初始化 (推荐)
echo   activate.bat
echo   xhs init
echo.
echo   :: 以后每次使用:
echo   activate.bat
echo   xhs search "关键词"
echo.
pause
