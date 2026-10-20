"""
etf_analytics.py - 台股主動型與槓桿正2 ETF 多週期報酬率、Beta、Alpha 與風險指標計算引擎
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

from etf_fetcher import get_all_etf_info, fetch_all_tw_etfs


@dataclass
class ETFPerformance:
    ticker: str
    name: str
    category: str
    etf_type: str
    description: str
    date: str
    current_price: float
    change: float
    pct_change_1d: float
    
    # 多週期報酬率 (%)
    return_1w: float
    return_1m: float
    return_3m: float
    return_ytd: float
    return_1y: float
    
    # 風險與操盤指標
    volatility_ann: float      # 年化波動度 (%)
    max_drawdown: float        # 最大回撤 MDD (%)
    sharpe_ratio: float        # 夏普值
    beta: float                # 對標大盤 Beta 係數
    alpha_1m: float            # 近 1 個月對標大盤 Alpha (%)
    manager_win_rate: float    # 經理人戰勝大盤勝率 (%)
    
    # 技術面狀態
    sma_5: float
    sma_20: float
    sma_60: float
    bias_20: float             # 20MA 月線乖離率 (%)
    bias_5: float              # 5MA 週線乖離率 (%)
    ma_trend: str              # 多頭排列 / 偏多站上月線 / 偏空跌破月線 / 空頭排列
    rsi_14: float
    macd_osc: float
    k_9: float
    d_9: float
    volume: float
    atr_14: float


def compute_etf_metrics(etf_df: pd.DataFrame, benchmark_df: pd.DataFrame, info: dict) -> ETFPerformance:
    """
    計算單檔 ETF 之多週期報酬率、Alpha、Beta 與技術指標
    """
    df = etf_df.copy().sort_index()
    n = len(df)
    if n < 2:
        raise ValueError(f"數據不足 ({n} 筆)")

    latest_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    curr_price = float(latest_row["Close"])
    prev_price = float(prev_row["Close"])
    change = curr_price - prev_price
    pct_1d = (change / prev_price) * 100.0

    # 1. 多週期報酬率計算
    def get_period_return(days: int) -> float:
        if n > days:
            past_price = float(df["Close"].iloc[-(days + 1)])
            return round(((curr_price - past_price) / past_price) * 100.0, 2)
        elif n > 1:
            first_price = float(df["Close"].iloc[0])
            return round(((curr_price - first_price) / first_price) * 100.0, 2)
        return 0.0

    ret_1w = get_period_return(5)
    ret_1m = get_period_return(20)
    ret_3m = get_period_return(60)
    ret_1y = get_period_return(250)

    # YTD 報酬率
    current_year = df.index[-1].year
    ytd_df = df[df.index.year == current_year]
    if len(ytd_df) >= 2:
        ytd_start_price = float(ytd_df["Close"].iloc[0])
        ret_ytd = round(((curr_price - ytd_start_price) / ytd_start_price) * 100.0, 2)
    else:
        ret_ytd = pct_1d

    # 2. 均線與趨勢
    sma5 = float(df["Close"].rolling(5).mean().iloc[-1]) if n >= 5 else curr_price
    sma20 = float(df["Close"].rolling(20).mean().iloc[-1]) if n >= 20 else curr_price
    sma60 = float(df["Close"].rolling(60).mean().iloc[-1]) if n >= 60 else sma20

    bias_20 = round(((curr_price - sma20) / (sma20 + 1e-9)) * 100.0, 2)
    bias_5 = round(((curr_price - sma5) / (sma5 + 1e-9)) * 100.0, 2)

    if curr_price > sma5 > sma20 > sma60:
        ma_trend = "🔥 多頭排列"
    elif curr_price > sma20 and sma5 > sma20:
        ma_trend = "📈 站上月線偏多"
    elif curr_price < sma5 < sma20 < sma60:
        ma_trend = "❄️ 空頭排列"
    elif curr_price < sma20:
        ma_trend = "📉 跌破月線偏弱"
    else:
        ma_trend = "⏸️ 區間震盪整理"

    # 3. RSI(14)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    rsi14 = float(100 - (100 / (1 + rs)).iloc[-1]) if n >= 14 else 50.0

    # 4. MACD(12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_osc = float(((dif - dea) * 2).iloc[-1])

    # 5. KD(9, 3, 3)
    low_min = df["Low"].rolling(9).min()
    high_max = df["High"].rolling(9).max()
    rsv = ((df["Close"] - low_min) / (high_max - low_min + 1e-9) * 100).fillna(50)
    k_val, d_val = 50.0, 50.0
    for r in rsv:
        k_val = (2/3) * k_val + (1/3) * r
        d_val = (2/3) * d_val + (1/3) * k_val

    # 6. ATR(14)
    high_low = df["High"] - df["Low"]
    high_pc = (df["High"] - df["Close"].shift(1)).abs()
    low_pc = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1]) if n >= 14 else curr_price * 0.015

    # 7. 波動度與最大回撤
    daily_rets = df["Close"].pct_change().dropna()
    vol_ann = float(daily_rets.std() * np.sqrt(252) * 100.0) if len(daily_rets) > 5 else 15.0
    
    cum_equity = (1 + daily_rets).cumprod()
    peak = cum_equity.cummax()
    dd = (cum_equity - peak) / peak * 100.0
    max_dd = float(dd.min()) if len(dd) > 0 else 0.0

    # 8. 夏普值 (假設無風險利率 1.5%)
    rf_daily = 0.015 / 252
    excess = daily_rets - rf_daily
    sharpe = float((excess.mean() / (daily_rets.std() + 1e-9)) * np.sqrt(252)) if len(daily_rets) > 5 else 0.0

    # 9. Beta、Alpha 與 經理人勝率 (vs Benchmark)
    beta = 1.0
    alpha_1m = 0.0
    manager_win_rate = 50.0  # 預設基準
    if benchmark_df is not None and len(benchmark_df) >= 20:
        aligned_bench = benchmark_df["Close"].reindex(df.index).ffill().bfill()
        bench_rets = aligned_bench.pct_change().dropna()
        common_idx = daily_rets.index.intersection(bench_rets.index)

        if len(common_idx) >= 10:
            e_rets = daily_rets.loc[common_idx]
            b_rets = bench_rets.loc[common_idx]
            cov = np.cov(e_rets, b_rets)[0][1]
            var_b = np.var(b_rets)
            beta = float(cov / (var_b + 1e-9)) if var_b > 0 else 1.0

            # 1個月 Alpha: ETF 1M Return - Benchmark 1M Return
            bench_1m_ret = float(((aligned_bench.iloc[-1] - aligned_bench.iloc[-min(20, len(aligned_bench))]) / aligned_bench.iloc[-min(20, len(aligned_bench))]) * 100)
            alpha_1m = round(ret_1m - bench_1m_ret, 2)

            # 經理人戰勝大盤勝率 (Beat Benchmark Win Rate): 日報酬優於大盤的天數佔比
            beat_days = int((e_rets > b_rets).sum())
            total_days = len(common_idx)
            manager_win_rate = round((beat_days / total_days) * 100.0, 1) if total_days > 0 else 50.0

    return ETFPerformance(
        ticker=info["ticker"],
        name=info["name"],
        category=info.get("category", "ETF"),
        etf_type=info.get("type", "主動式ETF"),
        description=info.get("description", ""),
        date=df.index[-1].strftime("%Y-%m-%d"),
        current_price=round(curr_price, 2),
        change=round(change, 2),
        pct_change_1d=round(pct_1d, 2),
        return_1w=ret_1w,
        return_1m=ret_1m,
        return_3m=ret_3m,
        return_ytd=ret_ytd,
        return_1y=ret_1y,
        volatility_ann=round(vol_ann, 1),
        max_drawdown=round(max_dd, 1),
        sharpe_ratio=round(sharpe, 2),
        beta=round(beta, 2),
        alpha_1m=alpha_1m,
        manager_win_rate=manager_win_rate,
        sma_5=round(sma5, 2),
        sma_20=round(sma20, 2),
        sma_60=round(sma60, 2),
        bias_20=bias_20,
        bias_5=bias_5,
        ma_trend=ma_trend,
        rsi_14=round(rsi14, 1),
        macd_osc=round(macd_osc, 3),
        k_9=round(k_val, 1),
        d_9=round(d_val, 1),
        volume=float(latest_row.get("Volume", 0)),
        atr_14=round(atr14, 2)
    )


def calculate_all_performances(force_reload: bool = False) -> list[ETFPerformance]:
    """計算全部主動型與正2 ETF 之即時與歷史績效"""
    all_info = get_all_etf_info()
    data_dict = fetch_all_tw_etfs(period="1y", force_reload=force_reload)
    bench_tw = data_dict.get("^TWII")

    results = []
    for info in all_info:
        ticker = info["ticker"]
        df = data_dict.get(ticker)
        if df is not None and len(df) >= 2:
            try:
                # 依標的選擇基準指數 (美股正2標的對標 ^IXIC)
                bench = data_dict.get(info.get("benchmark", "^TWII"), bench_tw)
                perf = compute_etf_metrics(df, bench, info)
                results.append(perf)
            except Exception as e:
                logger.warning(f"Error computing metrics for {ticker}: {e}")

    return results


if __name__ == "__main__":
    print("Testing ETF analytics...")
    perfs = calculate_all_performances()
    print(f"Computed metrics for {len(perfs)} ETFs:")
    for p in perfs[:5]:
        print(f"[{p.etf_type}] {p.ticker} {p.name}: Price={p.current_price} (1D:{p.pct_change_1d:+.2f}%, 1M:{p.return_1m:+.2f}%, YTD:{p.return_ytd:+.2f}%, Trend={p.ma_trend})")
