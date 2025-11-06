@echo off
REM TaskFlux Bot Launcher for Windows
echo ========================================
echo   TaskFlux Bot Launcher
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo Starting TaskFlux Bot...
echo.
echo Press Ctrl+C to stop the bot
echo.

python taskflux_bot.py

pause
