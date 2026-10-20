@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在啟動台股主動型與槓桿正2 ETF 網頁看板 (http://localhost:8503)...
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app_etf.py" --server.port 8503
if %ERRORLEVEL% NEQ 0 pause
