@echo off
chcp 65001 >nul

title MiniMax AI 生成工具 (Qt)

echo.
echo ========================================
echo   MiniMax AI 生成工具 v1.0.0 (Qt版)
echo   支持语音/图像/视频/音乐生成
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

:: 安装依赖
echo [1/2] 检查依赖...
pip install PySide6 requests -q 2>nul

:: 启动 Qt 应用
echo [2/2] 启动 Qt 应用...
start "MiniMax AI" /wait python -m src.qt_main

:: 检查退出码
if %errorlevel% neq 0 (
    echo.
    echo [错误] Qt 应用异常退出，错误码: %errorlevel%
    pause
)

exit
