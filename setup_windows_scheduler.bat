@echo off
chcp 65001 >nul
title 設定 Windows 本機每日 08:50 LINE 推播排程
cd /d "%~dp0"

echo ========================================================
echo   設定 Windows 本機每日 08:50 準時 LINE 推播排程
echo   (本機精確觸發、0秒延遲、不受 GitHub Actions 塞車影響)
echo ========================================================
echo.

set SCRIPT_PATH=%~dp0send_daily_push_dip.py
set PYTHON_PATH=%~dp0.venv\Scripts\python.exe

echo 正在註冊 Windows 排程任務【TAIEX_ETF_Dip_LINE_Push】(週一至週五 早上 08:50)...
schtasks /create /tn "TAIEX_ETF_Dip_LINE_Push" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:50 /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo ✅ 恭喜！Windows 工作排程已建立成功！
    echo 每週一至週五早上 08:50 將準時執行並發送 LINE 推播到您的手機。
    echo ========================================================
) else (
    echo.
    echo ⚠️ 建立失敗：若權限不足，請對本批次檔點擊右鍵 ➜ 選擇「以系統管理員身分執行」。
)

echo.
pause
