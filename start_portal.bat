@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================================
echo 🧭 台股量化投資決策總指揮中樞 (Master Hub All-in-One)
echo.
echo 💻 電腦本機存取網址:   http://localhost:8500
echo 📱 iPhone 手機存取網址: http://10.30.1.19:8500 (連同一個 Wi-Fi 即可)
echo 🔒 系統已啟用專屬密碼鎖定保護 (預設初始密碼為: 8888)
echo    ※ 即使同 Wi-Fi 別人連入，無密碼也無法查看任何資料！
echo =======================================================================
echo.
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app_portal.py" --server.port 8500 --server.address 0.0.0.0
if %ERRORLEVEL% NEQ 0 pause
