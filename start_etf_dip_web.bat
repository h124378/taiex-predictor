@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================================
echo 🇹🇼 台股 ETF 相對低點淘金與金字塔分批建倉系統 (Dip Hunter Edition)
echo 網頁伺服器啟動於: http://localhost:8502 (與 8501 獨立並存)
echo =======================================================================
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app_etf_dip.py" --server.port 8502
if %ERRORLEVEL% NEQ 0 pause
