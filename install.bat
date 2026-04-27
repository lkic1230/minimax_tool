@echo off
setlocal
chcp 65001 >nul
echo ========================================
echo   MiniMax AI 工具 - 环境部署
echo ========================================
echo.

echo [1/3] 正在安装依赖包（使用清华镜像源）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败！
    pause
    exit /b 1
)

echo.
echo [2/3] 正在安装工具（使用清华镜像源，开发模式）...
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo.
    echo [错误] 工具安装失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 正在绑定当前设备并记录 MAC 指纹...
python -m minimax_tool.src.cli config bind-device

if errorlevel 1 (
    echo.
    echo [错误] 设备绑定失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 启动方式:
echo   Qt应用: run-qt.bat
echo   CLI:    python -m minimax_tool.src.cli --help
echo.
pause
