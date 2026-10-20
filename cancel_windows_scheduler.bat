@echo off
chcp 65001 >nul
title 移除 Windows 本機每日 LINE 推播排程
echo 正在刪除 Windows 排程任務【TAIEX_ETF_Dip_LINE_Push】...
schtasks /delete /tn "TAIEX_ETF_Dip_LINE_Push" /f
echo.
pause
