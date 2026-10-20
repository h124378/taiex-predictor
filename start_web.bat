@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在啟動加權指數大盤網頁儀表板 (http://localhost:8501)...
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app.py"
if %ERRORLEVEL% NEQ 0 pause
