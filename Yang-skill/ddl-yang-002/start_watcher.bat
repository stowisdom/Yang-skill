@echo off
chcp 65001 >nul
echo.
echo ==========================================
echo   DDL Watcher - 任务文件自动监听
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装或未添加到 PATH
    pause
    exit /b 1
)

:: 检查 watchdog
echo 检查依赖...
python -c "import watchdog" >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装 watchdog...
    pip install watchdog
)

:: 启动监听
echo.
cd /d "%~dp0"
python ddl_watcher.py

echo.
pause
