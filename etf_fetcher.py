"""
etf_fetcher.py - 台灣全部主動型ETF (帶A/D) 與槓桿正2 ETF (帶L) 數據抓取與快取模組
支援自 TWSE / TPEx OpenAPI 自動同步全市場最新掛牌主動式 ETF。
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
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache", "etfs")
os.makedirs(CACHE_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "tw_etf_universe.json")


def load_etf_universe() -> dict:
    """載入主動型與正2 ETF 清單"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {CONFIG_PATH}: {e}")
    return {"active_etfs": [], "leveraged_2x_etfs": []}


def save_etf_universe(universe: dict) -> bool:
    """儲存 ETF 清單"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(universe, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {CONFIG_PATH}: {e}")
        return False


def sync_official_etf_universe() -> dict:
    """
    自 TWSE 與 TPEx OpenAPI 即時自動同步全台灣所有掛牌之主動式 ETF (帶A/D) 與槓桿正2 (帶L)
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    active_etfs = []
    leveraged_2x_etfs = []
    seen = set()

    try:
        # 1. TWSE
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        r_twse = requests.get(url_twse, headers=headers, timeout=8)
        if r_twse.status_code == 200:
            for d in r_twse.json():
                code = str(d.get("Code", "")).strip()
                name = str(d.get("Name", "")).strip()
                if (code.startswith("00") or code.startswith("01") or code.startswith("02")) and code not in seen:
                    # 僅保留主動式股票型 (帶A)
                    if code.endswith("A") or ("主動" in name and not code.endswith("D") and "債" not in name):
                        cat = "主動式股票型 (A)"
                        active_etfs.append({
                            "ticker": f"{code}.TW",
                            "name": name,
                            "category": cat,
                            "benchmark": "^TWII",
                            "description": f"台灣上市主動式股票型ETF ({name})"
                        })
                        seen.add(code)
                    elif code.endswith("L") or "正2" in name:
                        cat = "台股槓桿正2" if any(w in name for w in ["台灣", "加權", "台50"]) else "海外/商品正2"
                        bench = "^TWII" if cat == "台股槓桿正2" else "^IXIC" if "NASDAQ" in name else "^GSPC"
                        leveraged_2x_etfs.append({
                            "ticker": f"{code}.TW",
                            "name": name,
                            "category": cat,
                            "benchmark": bench,
                            "description": f"台灣上市槓桿正2 ETF ({name})"
                        })
                        seen.add(code)

        # 2. TPEx
        url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        r_tpex = requests.get(url_tpex, headers=headers, timeout=8)
        if r_tpex.status_code == 200:
            for d in r_tpex.json():
                code = str(d.get("SecuritiesCompanyCode", "")).strip()
                name = str(d.get("CompanyName", "")).strip()
                if (code.startswith("00") or code.startswith("01") or code.startswith("02")) and code not in seen:
                    if code.endswith("A") or ("主動" in name and not code.endswith("D") and "債" not in name):
                        cat = "主動式股票型 (A)"
                        active_etfs.append({
                            "ticker": f"{code}.TWO",
                            "name": name,
                            "category": cat,
                            "benchmark": "^TWII",
                            "description": f"櫃買上櫃主動式股票型ETF ({name})"
                        })
                        seen.add(code)
                    elif code.endswith("L") or "正2" in name:
                        leveraged_2x_etfs.append({
                            "ticker": f"{code}.TWO",
                            "name": name,
                            "category": "海外/商品正2",
                            "benchmark": "^TWII",
                            "description": f"櫃買上櫃槓桿正2 ETF ({name})"
                        })
                        seen.add(code)

        if active_etfs and leveraged_2x_etfs:
            universe = {"active_etfs": active_etfs, "leveraged_2x_etfs": leveraged_2x_etfs}
            save_etf_universe(universe)
            return universe
    except Exception as e:
        logger.warning(f"Failed to auto-sync OpenAPI: {e}")

    return load_etf_universe()


def get_all_etf_info() -> list[dict]:
    """獲取全部主動型與正2標的清單"""
    uni = load_etf_universe()
    if not uni.get("active_etfs"):
        uni = sync_official_etf_universe()

    items = []
    for item in uni.get("active_etfs", []):
        item["type"] = "主動式ETF"
        items.append(item)
    for item in uni.get("leveraged_2x_etfs", []):
        item["type"] = "槓桿正2"
        items.append(item)
    return items


_TWSE_DAILY_MAP = {}

def get_twse_daily_map() -> dict:
    global _TWSE_DAILY_MAP
    if _TWSE_DAILY_MAP:
        return _TWSE_DAILY_MAP
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        r = requests.get(url_twse, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            _TWSE_DAILY_MAP = {d["Code"]: d for d in r.json() if "Code" in d}
    except Exception as e:
        logger.warning(f"Error fetching TWSE daily map: {e}")
    return _TWSE_DAILY_MAP


def fetch_single_etf(ticker: str, period: str = "1y", force_reload: bool = False) -> pd.DataFrame:
    """抓取單一 ETF 歷史價格數據，並由證交所官方日數據自動填補缺漏交易日"""
    safe_name = ticker.replace("^", "").replace("=", "_").replace(".", "_")
    cache_file = os.path.join(CACHE_DIR, f"{safe_name}.parquet")
    now = time.time()
    cache_ttl = 1800

    if not force_reload and os.path.exists(cache_file):
        if now - os.path.getmtime(cache_file) < cache_ttl:
            try:
                df = pd.read_parquet(cache_file)
                if not df.empty:
                    return df
            except Exception:
                pass

    try:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=False)
        if data.empty:
            if ticker.endswith(".TW"):
                alt_ticker = ticker.replace(".TW", ".TWO")
                data = yf.download(alt_ticker, period=period, progress=False, auto_adjust=False)
            elif ticker.endswith(".TWO"):
                alt_ticker = ticker.replace(".TWO", ".TW")
                data = yf.download(alt_ticker, period=period, progress=False, auto_adjust=False)

        if data.empty:
            if os.path.exists(cache_file):
                return pd.read_parquet(cache_file)
            return pd.DataFrame()

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        data.index = pd.to_datetime(data.index).tz_localize(None)
        data = data.sort_index().dropna(subset=["Close"])

        # 官方交易所資料補齊：若 Yahoo Finance 遺漏交易日 (如 2026-09-03)，由證交所資料自動精準補正
        base_code = ticker.split(".")[0].replace("^", "")
        twse_map = get_twse_daily_map()
        if base_code in twse_map:
            tw_item = twse_map[base_code]
            tw_date_raw = str(tw_item.get("Date", ""))
            if len(tw_date_raw) == 7:
                try:
                    tw_year = int(tw_date_raw[:3]) + 1911
                    tw_month = int(tw_date_raw[3:5])
                    tw_day = int(tw_date_raw[5:])
                    tw_dt = pd.to_datetime(f"{tw_year}-{tw_month:02d}-{tw_day:02d}")
                    if tw_dt not in data.index and tw_item.get("ClosingPrice"):
                        c_val = float(tw_item["ClosingPrice"])
                        o_val = float(tw_item.get("OpeningPrice") or c_val)
                        h_val = float(tw_item.get("HighestPrice") or c_val)
                        l_val = float(tw_item.get("LowestPrice") or c_val)
                        v_val = float(tw_item.get("TradeVolume") or 0)
                        row = pd.Series({"Open": o_val, "High": h_val, "Low": l_val, "Close": c_val, "Volume": v_val}, name=tw_dt)
                        data.loc[tw_dt] = row
                        data = data.sort_index()
                except Exception:
                    pass

        data.to_parquet(cache_file)
        return data
    except Exception as e:
        logger.warning(f"Failed to fetch {ticker}: {e}")
        if os.path.exists(cache_file):
            return pd.read_parquet(cache_file)
        return pd.DataFrame()


def fetch_all_tw_etfs(period: str = "1y", force_reload: bool = False) -> dict[str, pd.DataFrame]:
    """批次獲取所有台灣主動型 (帶A/D) 與正2 (帶L) 標的數據"""
    all_info = get_all_etf_info()
    all_tickers = [item["ticker"] for item in all_info]
    
    benchmarks = ["^TWII", "^IXIC", "^GSPC"]
    for b in benchmarks:
        if b not in all_tickers:
            all_tickers.append(b)

    results = {}
    for t in all_tickers:
        df = fetch_single_etf(t, period=period, force_reload=force_reload)
        if not df.empty:
            results[t] = df
    return results


def add_custom_etf(ticker: str, name: str, category: str, description: str = "") -> bool:
    """動態新增自訂 ETF 到標的池"""
    uni = load_etf_universe()
    if not ticker.endswith(".TW") and not ticker.endswith(".TWO") and not ticker.startswith("^"):
        ticker = f"{ticker}.TW"

    target_group = "active_etfs" if ("A" in ticker.upper() or "D" in ticker.upper()) else "leveraged_2x_etfs"
    
    for group in ["active_etfs", "leveraged_2x_etfs"]:
        for item in uni.get(group, []):
            if item["ticker"].upper() == ticker.upper():
                return False

    new_item = {
        "ticker": ticker.upper(),
        "name": name,
        "category": category,
        "benchmark": "^TWII",
        "description": description or f"使用者自訂追蹤標的 {name}"
    }

    if target_group not in uni:
        uni[target_group] = []
    uni[target_group].append(new_item)
    return save_etf_universe(uni)


if __name__ == "__main__":
    print("Testing etf_fetcher with complete official universe...")
    uni = sync_official_etf_universe()
    print(f"Synced Active ETFs: {len(uni['active_etfs'])}, 2X ETFs: {len(uni['leveraged_2x_etfs'])}")
    data = fetch_all_tw_etfs(period="1mo")
    print(f"Successfully downloaded data for {len(data)} tickers!")
