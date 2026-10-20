"""
send_daily_push_dip.py - 每日自動執行並發送【相對低點淘金版 (金字塔建倉)】LINE 推播快訊腳本
可用於 GitHub Actions 或 Windows 工作排程器每日自動執行。
"""
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from etf_advisory_dip import evaluate_all_etfs_dip
from data_fetcher import build_aligned_dataset
from predictor import TAIEXPredictor
from notifier_etf import (
    load_push_config, generate_line_dip_push_message,
    send_line_bot_message, send_line_notify
)


def run_dip_push():
    print("=" * 50)
    print("💎 台股 ETF 相對低點淘金 (金字塔分批建倉) LINE 推播腳本")
    print("=" * 50)

    print("[1/3] 正在載入推播金鑰設定...")
    cfg = load_push_config()
    
    # 支援 GitHub Actions 環境變數 (Secrets) 覆蓋
    env_token = os.environ.get("LINE_CHANNEL_TOKEN")
    env_uid = os.environ.get("LINE_USER_ID")
    env_notify = os.environ.get("LINE_NOTIFY_TOKEN")

    if env_token and env_uid:
        cfg["mode"] = "bot"
        cfg["line_channel_token"] = env_token
        cfg["line_user_id"] = env_uid
    elif env_notify:
        cfg["mode"] = "notify"
        cfg["line_notify_token"] = env_notify

    if not cfg:
        print("❌ 尚未設定 LINE 推播金鑰！請先至 Web 介面側邊欄填寫或設定 GitHub Secrets。")
        return False

    print("[2/3] 正在計算台股大盤勝率與 36 檔主動型/正2 ETF 低點淘金指標...")
    try:
        raw_df = build_aligned_dataset(period="5y", force_reload=False)
        predictor = TAIEXPredictor()
        feats_df = predictor.build_feature_dataframe(raw_df)
        taiex_res = predictor.predict_latest(feats_df)
        print(f"  • 大盤明日上漲勝率: {taiex_res.prob_up:.1f}% ｜ 建議持股: {taiex_res.suggested_position}")
    except Exception as e:
        print(f"⚠️ 計算大盤勝率異常: {e}")
        taiex_res = None

    dip_advisories = evaluate_all_etfs_dip(force_reload=False)
    msg = generate_line_dip_push_message(dip_advisories, taiex_res)
    print("\n----- 推播訊息預覽 -----\n" + msg + "\n------------------------\n")

    print("[3/3] 正在發送 LINE 訊息...")
    mode = cfg.get("mode", "bot")
    if mode == "bot":
        token = cfg.get("line_channel_token", "")
        uid = cfg.get("line_user_id", "")
        if not token or not uid:
            print("❌ LINE Bot Token 或 User ID 尚未填寫！")
            return False
        ok, res = send_line_bot_message(token, uid, msg)
        print(f"發送結果: {'✅ 成功' if ok else '❌ 失敗'} - {res}")
        return ok
    else:
        token = cfg.get("line_notify_token", "")
        if not token:
            print("❌ LINE Notify Token 尚未填寫！")
            return False
        ok, res = send_line_notify(token, msg)
        print(f"發送結果: {'✅ 成功' if ok else '❌ 失敗'} - {res}")
        return ok


if __name__ == "__main__":
    success = run_dip_push()
    if not success:
        sys.exit(1)
