@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set BIN_NAME=xiaohongshu-mcp-windows-amd64.exe

if not exist "%BIN_NAME%" (
    echo [mcp] 二进制不存在: %BIN_NAME%
    echo [mcp] 请运行: xhs server install
    pause
    exit /b 1
)

:: 检查是否已在运行
tasklist /FI "IMAGENAME eq %BIN_NAME%" /NH 2>nul | find /i "%BIN_NAME%" >nul
if %errorlevel% equ 0 (
    echo [mcp] Already running
    exit /b 0
)

:: 设置端口和代理
if not defined MCP_PORT set MCP_PORT=18060
set COOKIES_PATH=%~dp0cookies.json

echo [mcp] Starting %BIN_NAME% on port %MCP_PORT%...
start /b "" "%~dp0%BIN_NAME%" -port :%MCP_PORT% > mcp.log 2>&1
echo [mcp] Started
