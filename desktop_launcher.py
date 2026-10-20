"""
desktop_launcher.py - 桌面原生獨立視窗啟動器 (Native Windows Desktop App)
"""
import sys
import os
import time
import socket
import subprocess
import webview

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
                s.settimeout(0.5)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    predictor_dir = os.path.join(base_dir, "taiex_predictor")
    if not os.path.exists(predictor_dir):
        predictor_dir = base_dir

    python_exe = os.path.join(predictor_dir, ".venv", "Scripts", "python.exe")
    app_script = os.path.join(predictor_dir, "app_portal.py")

    target_port = 8500

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = [
        python_exe, "-m", "streamlit", "run",
        app_script,
        f"--server.port={target_port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.runOnSave=false"
    ]

    server_process = subprocess.Popen(
        cmd,
        cwd=predictor_dir,
        startupinfo=startupinfo,
        creationflags=creationflags
    )

    try:
        wait_for_server(target_port, timeout=20)
        url = f"http://127.0.0.1:{target_port}"

        window = webview.create_window(
            title="🇹🇼 台股量化投資決策總指揮中樞 - Desktop Edition",
            url=url,
            width=1440,
            height=900,
            min_size=(1024, 700),
            resizable=True,
            confirm_close=False,
            background_color='#0f172a'
        )
        webview.start()
    finally:
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
