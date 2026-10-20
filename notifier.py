"""
notifier.py - 每日預測報告生成與即時通知模組
支援產生 Markdown / HTML 報告、Line Notify 與 Discord / Telegram Webhook 整合。
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import logging
from datetime import datetime
from typing import Optional
import requests

from predictor import PredictionResult

logger = logging.getLogger(__name__)


def generate_markdown_report(res: PredictionResult) -> str:
    """產生格式優美且包含籌碼數據的 Markdown 每日預測報告"""
    emoji_map = {
        "強力買進": "🔴🚀",
        "偏多操作": "📈✨",
        "觀望盤整": "⏸️⚖️",
        "偏空警戒": "📉⚠️",
        "強力賣出": "🟢🚨"
    }
    
    emoji = "📊"
    for k, v in emoji_map.items():
        if k in res.signal:
            emoji = v
            break

    f_days_str = f"連買 {abs(res.foreign_consec_days)} 天" if res.foreign_consec_days > 0 else f"連賣 {abs(res.foreign_consec_days)} 天" if res.foreign_consec_days < 0 else "持平"

    lines = [
        f"# 🇹🇼 台灣加權指數每日預測與決策報告 ({res.date})",
        "",
        f"### **今日總結評定：{emoji} {res.signal}**",
        f"- **操作建議**：`{res.action}`",
        f"- **建議持股水位**：`{res.suggested_position}`",
        f"- **昨日收盤價**：**{res.current_close:,.2f}** ({res.change:+,.2f} / {res.pct_change:+.2f}%)",
        "",
        "---",
        "",
        "### 🎯 **AI 機率與四維度量化量表**",
        f"- **🤖 明日上漲機率**：`{res.prob_up:.1f}%`  |  **明日下跌機率**：`{res.prob_down:.1f}%`",
        f"- **📈 技術面共識評分**：`{res.tech_score:+.0f}` / 100",
        f"- **🏦 籌碼面量化評分**：`{res.chip_score:+.0f}` / 100",
        f"- **⚖️ 綜合多空量化分數**：`{res.composite_score:+.1f}` / 100",
        f"- **🧠 模型歷史預測準確率**：`{res.model_accuracy:.1f}%`",
        "",
        "---",
        "",
        "### 🏦 **三大法人現貨與台指期貨籌碼**",
        "| 籌碼項目 | 數值 | 說明 |",
        "| :--- | :---: | :--- |",
        f"| **外資現貨買賣超** | **`{res.foreign_net_buy:+.2f} 億`** | {f_days_str} |",
        f"| **投信現貨買賣超** | `{res.trust_net_buy:+.2f} 億` | 內資與 ETF 被動資金 |",
        f"| **自營商現貨買賣超** | `{res.dealer_net_buy:+.2f} 億` | 自行買賣與避險 |",
        f"| **三大法人合計買賣超** | **`{res.total_inst_net_buy:+.2f} 億`** | 現貨主力資金總動向 |",
        f"| **外資大台期貨淨 OI** | **`{res.tx_foreign_net_oi:+,d} 口`** | 台指期避險/多空攻擊部位 |",
        f"| **外資期貨多空比** | `{res.tx_foreign_ls_ratio:.2f}` | 多方口數 / 空方口數 |",
        "",
        "---",
        "",
        "### 🛡️ **關鍵點位與風控指引**",
        "| 項目 | 點位 | 說明 |",
        "| :--- | :---: | :--- |",
        f"| **預期今日震盪區間** | `{res.expected_low:,.1f} ~ {res.expected_high:,.1f}` | 根據當前波動率 (ATR) 推算 |",
        f"| **第一壓力位 (R1)** | `{res.resistance_1:,.1f}` | 突破則轉為強勢多頭 |",
        f"| **第一支撐位 (S1)** | `{res.support_1:,.1f}` | 回檔重要防守關卡 |",
        f"| **建議動態停損點** | **`{res.target_stop_loss:,.1f}`** | 跌破/突破請嚴格執行紀律 |",
        f"| **目標停利點位** | **`{res.target_take_profit:,.1f}`** | 達標可適度獲利入袋 |",
        "",
        "---",
        "",
        "### 💡 **核心決策理由與指標診斷**"
    ]

    for r in res.reasons:
        lines.append(f"- {r}")

    lines.extend([
        "",
        "---",
        "⚠️ *免責聲明：本報告由 AI 量化模型基於歷史數據運算生成，僅供研究參考，不代表投資保證或買賣依據。投資人應獨立判斷並自負盈虧。*"
    ])

    return "\n".join(lines)


def send_line_notify(token: str, message: str) -> bool:
    """發送 Line Notify 通知"""
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"message": message}
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Line Notify: {e}")
        return False


def send_discord_webhook(webhook_url: str, content: str) -> bool:
    """發送 Discord Webhook 通知"""
    payload = {"content": content}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        return r.status_code in [200, 204]
    except Exception as e:
        logger.error(f"Failed to send Discord Webhook: {e}")
        return False


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """發送 Telegram Bot 訊息"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
