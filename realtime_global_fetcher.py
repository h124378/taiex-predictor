"""
realtime_global_fetcher.py - 即時國際金融市場走勢與台股先導指標抓取模組 (高精度與 5 秒高頻刷新)
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
import numpy as np
import yfinance as yf

GLOBAL_MARKETS = [
    {"ticker": "TSM", "name": "台積電 ADR", "group": "美股龍頭", "desc": "台股夜盤與開盤絕對核心指標"},
    {"ticker": "NQ=F", "name": "那斯達克期貨", "group": "美股期貨", "desc": "全球科技股夜盤多空風向球"},
    {"ticker": "ES=F", "name": "標普500期貨", "group": "美股期貨", "desc": "美股大盤主力資金動向"},
    {"ticker": "YM=F", "name": "道瓊期貨", "group": "美股期貨", "desc": "美股傳統藍籌股動向"},
    {"ticker": "^SOX", "name": "費城半導體", "group": "美股指數", "desc": "台股電子權值股直接聯動"},
    {"ticker": "^VIX", "name": "恐慌指數 VIX", "group": "市場風險", "desc": "全球資金避險與波動情緒"},
    {"ticker": "TWD=X", "name": "美元 / 新台幣", "group": "匯率資金", "desc": "外資匯出入與熱錢水位"},
    {"ticker": "^N225", "name": "日經 225 指數", "group": "亞股連動", "desc": "亞洲科技與出口股連動"},
    {"ticker": "^KS11", "name": "韓國綜合指數", "group": "亞股連動", "desc": "記憶體與半導體競爭指標"},
    {"ticker": "GC=F", "name": "黃金期貨", "group": "大宗商品", "desc": "避險抗通膨資金偏好"},
    {"ticker": "CL=F", "name": "原油期貨 (WTI)", "group": "大宗商品", "desc": "全球通膨與能源成本風向"}
]


@dataclass
class GlobalQuote:
    ticker: str
    name: str
    group: str
    desc: str
    price: float
    change: float
    pct_change: float
    high: float
    low: float
    updated_at: str
    is_up: bool


def fetch_realtime_global_quotes() -> tuple[list[GlobalQuote], float, str]:
    """
    高精度獲取即時國際市場報價（精準以昨日收盤價計算當日漲跌幅）
    """
    tickers = [m["ticker"] for m in GLOBAL_MARKETS]
    now_str = datetime.now().strftime("%H:%M:%S")

    try:
        # 下載日K線獲取精確昨收價與今日價格
        daily_data = yf.download(tickers, period="5d", interval="1d", progress=False)
        
        close_df = daily_data["Close"] if isinstance(daily_data.columns, pd.MultiIndex) else daily_data
        high_df = daily_data["High"] if isinstance(daily_data.columns, pd.MultiIndex) else daily_data
        low_df = daily_data["Low"] if isinstance(daily_data.columns, pd.MultiIndex) else daily_data

        quotes = []
        sentiment_score = 0.0

        for item in GLOBAL_MARKETS:
            t = item["ticker"]
            price = 0.0
            pct_change = 0.0
            change = 0.0
            high_val = 0.0
            low_val = 0.0

            if t in close_df:
                s_close = close_df[t].dropna()
                if not s_close.empty:
                    price = float(s_close.iloc[-1])
                    if len(s_close) >= 2:
                        prev_close = float(s_close.iloc[-2])
                        change = price - prev_close
                        pct_change = (change / (prev_close + 1e-9)) * 100.0
                    else:
                        pct_change = 0.0
                        change = 0.0

            if t in high_df:
                s_high = high_df[t].dropna()
                high_val = float(s_high.iloc[-1]) if not s_high.empty else price

            if t in low_df:
                s_low = low_df[t].dropna()
                low_val = float(s_low.iloc[-1]) if not s_low.empty else price

            quote = GlobalQuote(
                ticker=t,
                name=item["name"],
                group=item["group"],
                desc=item["desc"],
                price=round(price, 2),
                change=round(change, 2),
                pct_change=round(pct_change, 2),
                high=round(high_val, 2),
                low=round(low_val, 2),
                updated_at=now_str,
                is_up=pct_change >= 0
            )
            quotes.append(quote)

            # 計算台股即時先導多空權重
            if t == "TSM":
                sentiment_score += np.clip(pct_change * 15.0, -35, 35)
            elif t == "NQ=F":
                sentiment_score += np.clip(pct_change * 15.0, -25, 25)
            elif t == "^SOX":
                sentiment_score += np.clip(pct_change * 12.0, -20, 20)
            elif t == "^VIX":
                sentiment_score -= np.clip(pct_change * 2.5, -10, 10)
            elif t == "TWD=X":
                sentiment_score -= np.clip(pct_change * 15.0, -10, 10)

        sentiment_score = float(np.clip(sentiment_score, -100.0, 100.0))

        if sentiment_score >= 30:
            diag = "🚀 國際市場全面偏多！台積電 ADR 與科技期貨大漲，台股開盤動能強勁！"
        elif sentiment_score >= 8:
            diag = "📈 國際市場溫和上漲，美股科技股延續反彈，有利電子權值股。"
        elif sentiment_score <= -30:
            diag = "🚨 國際市場重挫避險！台積電 ADR 與美指期貨大跌，留意開盤賣壓！"
        elif sentiment_score <= -8:
            diag = "📉 國際市場偏弱整理，半導體與科技期貨承壓，建議審慎防守。"
        else:
            diag = "⏸️ 國際市場震盪平盤，多空力道均衡，靜待方向突破。"

        return quotes, sentiment_score, diag

    except Exception as e:
        return [], 0.0, f"即時數據抓取異常: {e}"


if __name__ == "__main__":
    print("Testing calibrated realtime global quotes...")
    quotes, score, diag = fetch_realtime_global_quotes()
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Global Sentiment Score: {score:+.1f} / 100")
    print(f"Diagnosis: {diag}\n")
    for q in quotes:
        print(f"[{q.group:6s}] {q.name:12s} ({q.ticker:6s}): {q.price:9.2f} | 今日漲跌: {q.pct_change:+.2f}% (High:{q.high:.2f}, Low:{q.low:.2f})")
