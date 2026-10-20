@echo off
chcp 65001 >nul
title 執行台股 LINE 每日推播
cd /d "%~dp0"
echo 正在執行台股大盤勝率與量化推薦 LINE 推播...
.\.venv\Scripts\python.exe send_daily_push.py
echo.
pause
