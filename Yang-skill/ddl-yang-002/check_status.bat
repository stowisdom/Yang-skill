@echo off
chcp 65001 >nul
echo.
echo ==========================================
echo   DDL Watcher 状态检查
echo ==========================================
echo.

cd /d "%~dp0"
python ddl_watcher.py --status

echo.
pause
