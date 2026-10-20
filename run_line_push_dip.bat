@echo off
chcp 65001 >nul
title 執行台股 ETF 相對低點淘金 LINE 推播
cd /d "%~dp0"
echo ========================================================
echo 正在執行【台股大盤勝率 & 相對低點淘金 (金字塔建倉)】LINE 推播...
echo ========================================================
.\.venv\Scripts\python.exe send_daily_push_dip.py
echo.
pause
