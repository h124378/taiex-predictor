"""
indicators.py - 技術指標與籌碼指標計算與診斷引擎
包含移動平均線(MA)、MACD、RSI、KD、布林通道、ATR、三大法人買賣超與台指期貨OI診斷。
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import numpy as np


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """計算相對強弱指標 RSI (Wilder's Smoothing)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_kd(df: pd.DataFrame, n: int = 9, k_period: int = 3, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    """計算隨機指標 KD (9, 3, 3)"""
    low_min = df["Low"].rolling(window=n).min()
    high_max = df["High"].rolling(window=n).max()

    rsv = (df["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
    rsv = rsv.fillna(50)

    k_vals = []
    d_vals = []
    curr_k = 50.0
    curr_d = 50.0

    for r in rsv:
        if np.isnan(r):
            curr_k = 50.0
            curr_d = 50.0
        else:
            curr_k = (2/3) * curr_k + (1/3) * r
            curr_d = (2/3) * curr_d + (1/3) * curr_k
        k_vals.append(curr_k)
        d_vals.append(curr_d)

    return pd.Series(k_vals, index=df.index), pd.Series(d_vals, index=df.index)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算全套技術與籌碼分析指標
    """
    res = df.copy()

    # 1. 移動平均線 (SMA)
    for p in [5, 10, 20, 60, 120, 240]:
        if len(res) >= p:
            res[f"SMA_{p}"] = res["Close"].rolling(window=p).mean()
            res[f"Bias_{p}"] = ((res["Close"] - res[f"SMA_{p}"]) / res[f"SMA_{p}"]) * 100
        else:
            res[f"SMA_{p}"] = np.nan
            res[f"Bias_{p}"] = np.nan

    res["SMA_5_Slope"] = res["SMA_5"].pct_change(3) * 100
    res["SMA_20_Slope"] = res["SMA_20"].pct_change(5) * 100
    res["SMA_60_Slope"] = res["SMA_60"].pct_change(10) * 100

    # 均線多空發散度 (Spread)
    res["MA_Spread_5_20"] = ((res["SMA_5"] - res["SMA_20"]) / (res["SMA_20"] + 1e-9)) * 100
    res["MA_Spread_20_60"] = ((res["SMA_20"] - res["SMA_60"]) / (res["SMA_60"] + 1e-9)) * 100

    is_bull_ma = (
        (res["SMA_5"] > res["SMA_10"]) &
        (res["SMA_10"] > res["SMA_20"]) &
        (res["SMA_20"] > res["SMA_60"])
    )
    is_bear_ma = (
        (res["SMA_5"] < res["SMA_10"]) &
        (res["SMA_10"] < res["SMA_20"]) &
        (res["SMA_20"] < res["SMA_60"])
    )
    res["MA_Bull_Arranged"] = is_bull_ma.astype(int)
    res["MA_Bear_Arranged"] = is_bear_ma.astype(int)

    # 2. MACD
    ema12 = res["Close"].ewm(span=12, adjust=False).mean()
    ema26 = res["Close"].ewm(span=26, adjust=False).mean()
    res["MACD_DIF"] = ema12 - ema26
    res["MACD_DEA"] = res["MACD_DIF"].ewm(span=9, adjust=False).mean()
    res["MACD_OSC"] = (res["MACD_DIF"] - res["MACD_DEA"]) * 2
    res["MACD_OSC_Diff"] = res["MACD_OSC"].diff()
    res["MACD_Golden_Cross"] = ((res["MACD_DIF"] > res["MACD_DEA"]) & (res["MACD_DIF"].shift(1) <= res["MACD_DEA"].shift(1))).astype(int)
    res["MACD_Death_Cross"] = ((res["MACD_DIF"] < res["MACD_DEA"]) & (res["MACD_DIF"].shift(1) >= res["MACD_DEA"].shift(1))).astype(int)

    # 3. RSI
    res["RSI_6"] = calculate_rsi(res["Close"], period=6)
    res["RSI_14"] = calculate_rsi(res["Close"], period=14)

    # 4. KD
    res["K_9"], res["D_9"] = calculate_kd(res, n=9, k_period=3, d_period=3)
    res["KD_Golden_Cross"] = ((res["K_9"] > res["D_9"]) & (res["K_9"].shift(1) <= res["D_9"].shift(1))).astype(int)
    res["KD_Death_Cross"] = ((res["K_9"] < res["D_9"]) & (res["K_9"].shift(1) >= res["D_9"].shift(1))).astype(int)

    # 5. 布林通道
    bb_mean = res["Close"].rolling(window=20).mean()
    bb_std = res["Close"].rolling(window=20).std()
    res["BB_Middle"] = bb_mean
    res["BB_Upper"] = bb_mean + 2 * bb_std
    res["BB_Lower"] = bb_mean - 2 * bb_std
    res["BB_BandWidth"] = ((res["BB_Upper"] - res["BB_Lower"]) / (bb_mean + 1e-9)) * 100
    res["BB_PercentB"] = (res["Close"] - res["BB_Lower"]) / (res["BB_Upper"] - res["BB_Lower"] + 1e-9)

    # 6. ATR
    high_low = res["High"] - res["Low"]
    high_prev_close = (res["High"] - res["Close"].shift(1)).abs()
    low_prev_close = (res["Low"] - res["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    res["TR"] = tr
    res["ATR_14"] = tr.rolling(window=14).mean()
    res["ATR_Pct"] = (res["ATR_14"] / res["Close"]) * 100

    # 7. 成交量
    if "Volume" in res.columns:
        res["VMA_5"] = res["Volume"].rolling(window=5).mean()
        res["VMA_20"] = res["Volume"].rolling(window=20).mean()
        res["Vol_Ratio_5"] = res["Volume"] / (res["VMA_5"] + 1e-9)
        res["Vol_Ratio_20"] = res["Volume"] / (res["VMA_20"] + 1e-9)

    # 8. 收益與波動
    res["Return_1d"] = res["Close"].pct_change(1) * 100
    res["Return_3d"] = res["Close"].pct_change(3) * 100
    res["Return_5d"] = res["Close"].pct_change(5) * 100
    res["Volatility_20d"] = res["Return_1d"].rolling(20).std()

    # K 線實體與影線型態特徵
    body = (res["Close"] - res["Open"]).abs()
    candle_range = (res["High"] - res["Low"]).replace(0, np.nan)
    res["Candle_Body_Ratio"] = (body / candle_range).fillna(0.5)
    res["Candle_Upper_Shadow"] = ((res["High"] - res[["Close", "Open"]].max(axis=1)) / candle_range).fillna(0)
    res["Candle_Lower_Shadow"] = (((res[["Close", "Open"]].min(axis=1) - res["Low"])) / candle_range).fillna(0)

    # 9. 關鍵支撐與壓力點
    prev_high = res["High"].shift(1)
    prev_low = res["Low"].shift(1)
    prev_close = res["Close"].shift(1)
    pivot = (prev_high + prev_low + prev_close) / 3.0
    res["Pivot"] = pivot
    res["Resistance_1"] = 2 * pivot - prev_low
    res["Support_1"] = 2 * pivot - prev_high
    res["Resistance_2"] = pivot + (prev_high - prev_low)
    res["Support_2"] = pivot - (prev_high - prev_low)

    return res


def diagnose_indicators(df_with_ind: pd.DataFrame) -> list[dict]:
    """
    診斷各項技術與籌碼指標多空狀態
    """
    if df_with_ind.empty or len(df_with_ind) < 2:
        return []

    row = df_with_ind.iloc[-1]
    prev = df_with_ind.iloc[-2]
    diagnostics = []

    # 1. 均線排列 (Trend)
    close = row["Close"]
    sma5 = row.get("SMA_5", np.nan)
    sma20 = row.get("SMA_20", np.nan)
    sma60 = row.get("SMA_60", np.nan)

    if not np.isnan(sma5) and not np.isnan(sma20) and not np.isnan(sma60):
        if close > sma5 > sma20 > sma60:
            status = "極度偏多"
            score = 25
            desc = f"指數位於所有均線之上 ({close:.0f} > 5MA:{sma5:.0f} > 月線:{sma20:.0f} > 季線:{sma60:.0f})，均線呈多頭排列。"
        elif close > sma20 and sma5 > sma20:
            status = "偏多"
            score = 15
            desc = f"指數站穩月線 ({close:.0f} > 月線:{sma20:.0f})，短期 5MA 向上，多方掌控主導權。"
        elif close < sma5 < sma20 < sma60:
            status = "極度偏空"
            score = -25
            desc = f"指數失守所有均線 ({close:.0f} < 5MA:{sma5:.0f} < 月線:{sma20:.0f} < 季線:{sma60:.0f})，均線呈空頭排列。"
        elif close < sma20:
            status = "偏空"
            score = -15
            desc = f"指數跌破月線 ({close:.0f} < 月線:{sma20:.0f})，短中期均線蓋頭反壓。"
        else:
            status = "中立盤整"
            score = 0
            desc = f"指數在均線間震盪整理 (收盤:{close:.0f}, 月線:{sma20:.0f})。"
        diagnostics.append({"category": "趨勢均線", "status": status, "score": score, "desc": desc})

    # 2. MACD 動能
    dif = row.get("MACD_DIF", 0)
    dea = row.get("MACD_DEA", 0)
    osc = row.get("MACD_OSC", 0)
    prev_osc = prev.get("MACD_OSC", 0)

    if osc > 0 and osc > prev_osc:
        status = "偏多轉強"
        score = 20
        desc = f"MACD 紅柱持續擴大 (OSC: {osc:+.2f})，多方攻擊動能強勁。"
    elif osc > 0 and osc <= prev_osc:
        status = "高檔鈍化/縮小"
        score = 5
        desc = f"MACD 仍為紅柱 (OSC: {osc:+.2f})，但多方力道稍有減緩，留意高檔震盪。"
    elif osc < 0 and osc < prev_osc:
        status = "偏空轉強"
        score = -20
        desc = f"MACD 綠柱持續擴大 (OSC: {osc:+.2f})，空方殺盤動能擴大，宜避險。"
    elif osc < 0 and osc >= prev_osc:
        status = "空方收斂"
        score = -5
        desc = f"MACD 雖為綠柱 (OSC: {osc:+.2f})，但空方力道開始收斂，或有築底契機。"
    else:
        status = "中立"
        score = 0
        desc = f"MACD 走勢平緩 (OSC: {osc:+.2f})。"
    diagnostics.append({"category": "MACD 指標", "status": status, "score": score, "desc": desc})

    # 3. KD 轉折
    k = row.get("K_9", 50)
    d = row.get("D_9", 50)
    prev_k = prev.get("K_9", 50)
    prev_d = prev.get("D_9", 50)

    if k > d and prev_k <= prev_d and k < 40:
        status = "低檔黃金交叉"
        score = 20
        desc = f"KD 於低檔 ({k:.1f}/{d:.1f}) 出現黃金交叉，為強烈反彈買訊！"
    elif k > d and k > 80:
        status = "高檔超買/鈍化"
        score = 5
        desc = f"KD 處於高檔超買區 ({k:.1f}/{d:.1f})，強勢但隨時有回檔修乖離風險。"
    elif k > d:
        status = "偏多續行"
        score = 10
        desc = f"KD 向上發散 (K:{k:.1f} > D:{d:.1f})，短線多頭掌控節奏。"
    elif k < d and prev_k >= prev_d and k > 60:
        status = "高檔死亡交叉"
        score = -20
        desc = f"KD 於高檔 ({k:.1f}/{d:.1f}) 出現死亡交叉，為明確減碼防禦訊號！"
    elif k < d and k < 20:
        status = "低檔超賣"
        score = -5
        desc = f"KD 處於超賣區 ({k:.1f}/{d:.1f})，空方力竭隨時醞釀技術性反彈。"
    else:
        status = "偏空整理"
        score = -10
        desc = f"KD 向下發散 (K:{k:.1f} < D:{d:.1f})，短線偏弱。"
    diagnostics.append({"category": "KD 隨機指標", "status": status, "score": score, "desc": desc})

    # 4. RSI 強弱
    rsi14 = row.get("RSI_14", 50)
    if rsi14 >= 75:
        status = "超買警戒"
        score = -5
        desc = f"RSI(14) 達 {rsi14:.1f}，進入極度過熱超買區，慎防獲利了結賣壓。"
    elif rsi14 >= 55:
        status = "多方強勢"
        score = 15
        desc = f"RSI(14) 為 {rsi14:.1f}，位於 50 多空分界線上方且持續走強。"
    elif rsi14 <= 25:
        status = "超跌超賣"
        score = 10
        desc = f"RSI(14) 降至 {rsi14:.1f}，進入超賣恐慌區，具備短線反彈獲利空間。"
    elif rsi14 < 45:
        status = "空方弱勢"
        score = -15
        desc = f"RSI(14) 為 {rsi14:.1f}，落於 50 分界線下方，買盤力道疲弱。"
    else:
        status = "中立觀望"
        score = 0
        desc = f"RSI(14) 為 {rsi14:.1f}，多空力道均衡。"
    diagnostics.append({"category": "RSI 強弱", "status": status, "score": score, "desc": desc})

    # 5. 外資現貨籌碼 (Foreign Spot Chips)
    f_net = float(row.get("Foreign_Net_Buy", 0))
    f_days = int(row.get("Foreign_Consecutive_Days", 0))
    if f_net >= 120 or f_days >= 3:
        status = "外資大買加碼"
        score = 20
        desc = f"外資現貨強力買超 {f_net:+.1f} 億 (連買 {abs(f_days)} 天)，主力資金全力作多！"
    elif f_net >= 30:
        status = "外資溫和偏多"
        score = 10
        desc = f"外資現貨買超 {f_net:+.1f} 億，資金回流台股權值股。"
    elif f_net <= -150 or f_days <= -4:
        status = "外資重挫提款"
        score = -20
        desc = f"外資現貨大舉提款賣超 {f_net:+.1f} 億 (連賣 {abs(f_days)} 天)，權值股賣壓沉重！"
    elif f_net <= -40:
        status = "外資調節偏空"
        score = -10
        desc = f"外資現貨賣超 {f_net:+.1f} 億，資金流出。"
    else:
        status = "外資中性進出"
        score = 0
        desc = f"外資現貨小幅進出 ({f_net:+.1f} 億)，觀望意味濃。"
    diagnostics.append({"category": "外資現貨籌碼", "status": status, "score": score, "desc": desc})

    # 6. 台指期貨大台未平倉 (Futures Open Interest / OI)
    tx_f_oi = int(row.get("TX_Foreign_Net_OI", -15000))
    tx_ls = float(row.get("TX_Foreign_LS_Ratio", 1.0))
    if tx_f_oi >= 3000:
        status = "期貨強大多頭"
        score = 20
        desc = f"外資台指期未平倉呈【淨多單】{tx_f_oi:+,d} 口 (多空比 {tx_ls:.2f})，期現貨同步偏多！"
    elif tx_f_oi >= -15000:
        status = "期貨溫和偏多"
        score = 10
        desc = f"外資台指期淨空單處於低水位 ({tx_f_oi:,d} 口)，空方避險壓力極輕。"
    elif tx_f_oi <= -45000:
        status = "期貨重空警戒"
        score = -25
        desc = f"外資台指期淨空單高達 {tx_f_oi:,d} 口警戒水位 (多空比僅 {tx_ls:.2f})，壓抑大盤反彈！"
    elif tx_f_oi <= -30000:
        status = "期貨偏空防禦"
        score = -15
        desc = f"外資台指期淨空單達 {tx_f_oi:,d} 口，空方避險部位偏高，需提防壓低結算。"
    else:
        status = "期貨常態避險"
        score = 0
        desc = f"外資台指期淨空單 {tx_f_oi:,d} 口，落於常態避險區間。"
    diagnostics.append({"category": "台指期貨OI", "status": status, "score": score, "desc": desc})

    # 7. 美股 ADR 先導
    tsm_ret = row.get("TSMC_ADR_Return_1d", np.nan)
    sox_ret = row.get("SOX_Return_1d", np.nan)
    if not np.isnan(tsm_ret) or not np.isnan(sox_ret):
        tsm_val = tsm_ret if not np.isnan(tsm_ret) else 0.0
        sox_val = sox_ret if not np.isnan(sox_ret) else 0.0
        avg_us = (tsm_val * 0.6 + sox_val * 0.4)

        if avg_us >= 1.8:
            status = "美半導體大漲"
            score = 20
            desc = f"台積電 ADR 昨漲 {tsm_val:+.2f}%，費半大漲 {sox_val:+.2f}%，開盤預期激勵台股權值股！"
        elif avg_us <= -1.8:
            status = "美半導體重挫"
            score = -20
            desc = f"台積電 ADR 昨跌 {tsm_val:+.2f}%，費半大跌 {sox_val:+.2f}%，對台股電子權值股形成直接重擊！"
        elif avg_us >= 0.5:
            status = "美半導體偏多"
            score = 10
            desc = f"台積電 ADR ({tsm_val:+.2f}%) 與費半 ({sox_val:+.2f}%) 溫和收紅。"
        elif avg_us <= -0.5:
            status = "美半導體偏弱"
            score = -10
            desc = f"台積電 ADR ({tsm_val:+.2f}%) 與費半 ({sox_val:+.2f}%) 走弱收黑。"
        else:
            status = "美股平盤整理"
            score = 0
            desc = f"美股半導體昨夜平盤震盪 (ADR:{tsm_val:+.2f}%, 費半:{sox_val:+.2f}%)。"
        diagnostics.append({"category": "美股ADR領先", "status": status, "score": score, "desc": desc})

    return diagnostics
