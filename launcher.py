"""
launcher.py - 台灣股市量化決策系統總選單啟動器
包含：加權指數大盤預測、三大法人籌碼、台股主動型 (帶A) 與槓桿正2 (帶L) ETF 每日報酬與買賣建議
"""

import os
import sys
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable


def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 72)
        print("   🇹🇼 台灣股市 AI 決策系統：加權指數多空預測 ＆ 台股主動/正2 ETF 看板")
        print("=" * 72)
        print()
        print("  【主動型與正2 ETF 專區】")
        print("   [1] 啟動 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 網頁看板 (推薦)")
        print("   [2] 啟動 台股 ETF 相對低點淘金與金字塔分批建倉網頁看板 (Dip Hunter)")
        print("   [3] 終端機快速查看 主動型與正2 ETF 每日報酬排行榜 (CLI 模式)")
        print()
        print("  【台股加權指數大盤專區】")
        print("   [4] 啟動 台灣加權指數 每日多空預測與籌碼網頁儀表板")
        print("   [5] 終端機快速查看 加權指數預測與三大法人籌碼")
        print("   [6] 執行 大盤策略歷史步進式回測 (Walk-Forward Backtesting)")
        print()
        print("  【綜合功能】")
        print("   [7] 匯出今日全部 Markdown 分析日報")
        print("   [8] 退出系統")
        print()
        print("-" * 72)
        
        try:
            choice = input("請輸入選項 (1-8): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            break

        if choice == "1":
            print("\n正在啟動主動型與正2 ETF 網頁看板，請稍候...")
            print("瀏覽器將自動開啟 http://localhost:8501\n")
            try:
                subprocess.run([PYTHON_EXE, "-m", "streamlit", "run", os.path.join(CURRENT_DIR, "app_etf.py")])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "2":
            print("\n正在啟動 ETF 相對低點淘金與分批建倉看板，請稍候...")
            print("瀏覽器將自動開啟 http://localhost:8502\n")
            try:
                subprocess.run([PYTHON_EXE, "-m", "streamlit", "run", os.path.join(CURRENT_DIR, "app_etf_dip.py"), "--server.port", "8502"])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "3":
            print()
            try:
                subprocess.run([PYTHON_EXE, os.path.join(CURRENT_DIR, "cli_etf.py")])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "4":
            print("\n正在啟動加權指數大盤網頁儀表板，請稍候...")
            print("瀏覽器將自動開啟 http://localhost:8501\n")
            try:
                subprocess.run([PYTHON_EXE, "-m", "streamlit", "run", os.path.join(CURRENT_DIR, "app.py")])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "5":
            print()
            try:
                subprocess.run([PYTHON_EXE, os.path.join(CURRENT_DIR, "cli_predictor.py")])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "6":
            print("\n正在執行大盤策略歷史回測，請稍候...\n")
            try:
                subprocess.run([PYTHON_EXE, os.path.join(CURRENT_DIR, "backtest.py")])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "7":
            print("\n正在匯出今日全部 Markdown 日報...\n")
            try:
                subprocess.run([PYTHON_EXE, os.path.join(CURRENT_DIR, "cli_predictor.py"), "--export"])
                subprocess.run([PYTHON_EXE, os.path.join(CURRENT_DIR, "cli_etf.py"), "--export"])
            except KeyboardInterrupt:
                pass
            input("\n按 Enter 鍵返回主選單...")

        elif choice == "8":
            print("\n感謝使用，祝您投資順利、獲利滿滿！")
            break
        else:
            print("\n無效選項，請重新輸入！")
            input("按 Enter 鍵繼續...")


if __name__ == "__main__":
    main()
