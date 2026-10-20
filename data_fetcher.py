"""
data_fetcher.py - 台灣加權指數、跨市場數據與法人籌碼獲取與對齊模組
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
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

from chip_fetcher import fetch_institutional_chips

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 觀測標的代碼
TICKERS = {
    "TAIEX": "^TWII",      # 台灣加權指數
    "TSMC_ADR": "TSM",     # 台積電 ADR (美股，台股最重要領先指標)
    "SOX": "^SOX",         # 費城半導體指數
    "SP500": "^GSPC",      # 標普 500 指數
    "NASDAQ": "^IXIC",     # 那斯達克指數
    "USDTWD": "TWD=X",     # 美元兌新台幣匯率
    "TSMC_TW": "2330.TW",  # 台積電 (台股現貨)
}


def get_cache_path(ticker: str) -> str:
    safe_name = ticker.replace("^", "").replace("=", "_").replace(".", "_")
    return os.path.join(CACHE_DIR, f"{safe_name}.parquet")


def fetch_ticker_data(ticker: str, period: str = "5y", force_reload: bool = False) -> pd.DataFrame:
    """
    獲取單一標的歷史資料，支援快取與自動增量更新
    """
    cache_file = get_cache_path(ticker)
    now = time.time()
    cache_ttl = 1800  # 快取 30 分鐘

    if not force_reload and os.path.exists(cache_file):
        file_age = now - os.path.getmtime(cache_file)
        if file_age < cache_ttl:
            try:
                df = pd.read_parquet(cache_file)
                if not df.empty:
                    logger.info(f"Loaded {ticker} from cache ({len(df)} rows)")
                    return df
            except Exception as e:
                logger.warning(f"Error reading cache for {ticker}: {e}")

    logger.info(f"Fetching fresh data for {ticker} (period={period})...")
    try:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=False)
        if data.empty:
            logger.warning(f"No data returned for {ticker}")
            if os.path.exists(cache_file):
                return pd.read_parquet(cache_file)
            return pd.DataFrame()

        # 扁平化 MultiIndex (yfinance 新版常輸出 MultiIndex columns)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        # 整理欄位
        data.index = pd.to_datetime(data.index)
        data.index = data.index.tz_localize(None)  # 去除時區以便對齊
        data = data.sort_index()

        req_cols = ["Open", "High", "Low", "Close", "Volume"]
        for col in req_cols:
            if col not in data.columns:
                data[col] = np.nan

        data = data.dropna(subset=["Close"])
        data.to_parquet(cache_file)
        return data

    except Exception as e:
        logger.error(f"Failed to fetch {ticker}: {e}")
        if os.path.exists(cache_file):
            logger.info(f"Falling back to existing cache for {ticker}")
            return pd.read_parquet(cache_file)
        return pd.DataFrame()


def fetch_all_market_data(period: str = "5y", force_reload: bool = False) -> dict[str, pd.DataFrame]:
    """
    下載所有相關市場數據
    """
    market_data = {}
    for name, ticker in TICKERS.items():
        df = fetch_ticker_data(ticker, period=period, force_reload=force_reload)
        market_data[name] = df
    return market_data


def build_aligned_dataset(period: str = "5y", force_reload: bool = False) -> pd.DataFrame:
    """
    構建對齊後的跨市場與法人籌碼資料集
    """
    raw_data = fetch_all_market_data(period=period, force_reload=force_reload)
    taiex = raw_data.get("TAIEX")

    if taiex is None or taiex.empty:
        raise ValueError("無法獲取台灣加權指數 (^TWII) 資料！")

    df = pd.DataFrame(index=taiex.index)
    df["Open"] = taiex["Open"]
    df["High"] = taiex["High"]
    df["Low"] = taiex["Low"]
    df["Close"] = taiex["Close"]
    df["Volume"] = taiex["Volume"]
    if "Adj Close" in taiex.columns:
        df["Adj Close"] = taiex["Adj Close"]
    else:
        df["Adj Close"] = taiex["Close"]

    # 跨市場資料對齊（美股先導）
    for name in ["TSMC_ADR", "SOX", "SP500", "NASDAQ", "USDTWD", "TSMC_TW"]:
        m_df = raw_data.get(name)
        if m_df is not None and not m_df.empty:
            m_close = m_df["Close"].copy()
            m_return = m_close.pct_change() * 100

            aligned_close = m_close.reindex(df.index, method="ffill")
            aligned_return = m_return.reindex(df.index, method="ffill")

            df[f"{name}_Close"] = aligned_close
            df[f"{name}_Return_1d"] = aligned_return

    # 加入三大法人現貨與期貨未平倉籌碼特徵
    try:
        chips = fetch_institutional_chips(df, force_reload=force_reload)
        for col in chips.columns:
            df[col] = chips[col]
    except Exception as e:
        logger.warning(f"Error merging institutional chips: {e}")

    df = df.dropna(subset=["Close", "Open"])
    return df


def get_latest_market_snapshot() -> dict:
    """
    取得最新即時/昨日跨市場與籌碼概況摘要
    """
    data = fetch_all_market_data(period="1mo", force_reload=False)
    snapshot = {}

    for name, df in data.items():
        if df is not None and len(df) >= 2:
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            last_close = float(last_row["Close"])
            prev_close = float(prev_row["Close"])
            change = last_close - prev_close
            pct_change = (change / prev_close) * 100

            snapshot[name] = {
                "date": df.index[-1].strftime("%Y-%m-%d"),
                "close": last_close,
                "prev_close": prev_close,
                "change": change,
                "pct_change": pct_change,
                "high": float(last_row["High"]),
                "low": float(last_row["Low"]),
                "volume": float(last_row["Volume"]) if "Volume" in last_row else 0,
            }
        else:
            snapshot[name] = None

    # 加入最新籌碼摘要
    try:
        aligned = build_aligned_dataset(period="1mo", force_reload=False)
        last_row = aligned.iloc[-1]
        snapshot["CHIPS"] = {
            "Foreign_Net_Buy": float(last_row.get("Foreign_Net_Buy", 0)),
            "Trust_Net_Buy": float(last_row.get("Trust_Net_Buy", 0)),
            "Dealer_Net_Buy": float(last_row.get("Dealer_Net_Buy", 0)),
            "Total_Inst_Net_Buy": float(last_row.get("Total_Inst_Net_Buy", 0)),
            "TX_Foreign_Net_OI": int(last_row.get("TX_Foreign_Net_OI", 0)),
            "TX_Total_Inst_Net_OI": int(last_row.get("TX_Total_Inst_Net_OI", 0)),
            "TX_Foreign_LS_Ratio": float(last_row.get("TX_Foreign_LS_Ratio", 1.0)),
            "Foreign_Consecutive_Days": int(last_row.get("Foreign_Consecutive_Days", 0)),
            "Trust_Consecutive_Days": int(last_row.get("Trust_Consecutive_Days", 0)),
        }
    except Exception as e:
        logger.warning(f"Error adding chips snapshot: {e}")

    return snapshot


if __name__ == "__main__":
    print("Testing data fetcher with chips...")
    df = build_aligned_dataset(period="1y")
    print(f"Dataset shape: {df.shape}")
    print("Columns:", df.columns.tolist())
    snap = get_latest_market_snapshot()
    print("\nChips Snapshot:")
    print(snap.get("CHIPS"))
