"""
desktop_main.py - 台股量化投資決策總指揮中樞 (Windows 原生桌面視窗啟動器)
完全擺脫網頁瀏覽器模式，以獨立原生視窗 (Native Desktop App) 呈現，無網址列、無瀏覽器分頁、無黑底終端機！
"""

import sys
import os
import time
import socket
import subprocess
import threading
import webview

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable

def find_free_port(start_port=8500):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return 8500

def wait_for_server(port, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def main():
    target_port = find_free_port(8500)
    app_script = os.path.join(CURRENT_DIR, "app_portal.py")

    # 隱藏黑底視窗啟動背景 Streamlit 引擎
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW

    cmd = [
        PYTHON_EXE, "-m", "streamlit", "run",
        app_script,
        f"--server.port={target_port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.runOnSave=false"
    ]

    server_process = subprocess.Popen(
        cmd,
        cwd=CURRENT_DIR,
        startupinfo=startupinfo,
        creationflags=creationflags
    )

    try:
        # 等候伺服器就緒
        server_ready = wait_for_server(target_port, timeout=20)
        url = f"http://127.0.0.1:{target_port}"

        # 建立專屬 Windows 原生桌面軟體視窗 (免瀏覽器)
        window = webview.create_window(
            title="🇹🇼 台股量化投資決策總指揮中樞 - Desktop Edition",
            url=url,
            width=1400,
            height=900,
            min_size=(1024, 700),
            resizable=True,
            confirm_close=False,
            background_color='#0f172a'
        )

        webview.start()
    finally:
        # 當桌面視窗關閉時，乾淨關閉背景進程
        try:
            server_process.terminate()
            server_process.wait(timeout=3)
        except Exception:
            try:
                server_process.kill()
            except Exception:
                pass

if __name__ == "__main__":
    main()
