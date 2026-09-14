@echo off
rem Summarix: start the digest bot. Closing this window stops the bot.
title Summarix bot
cd /d "%~dp0"
chcp 65001 >nul

powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*run_bot.py*' }) { exit 1 }"
if errorlevel 1 (
    echo The bot is already running in another window.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found: .venv
    pause
    exit /b 1
)

set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo Summarix bot is starting. Keep this window open; close it to stop the bot.
echo.
".venv\Scripts\python.exe" run_bot.py

echo.
echo The bot has stopped.
pause
