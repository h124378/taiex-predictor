"""
etf_advisory_dip.py - 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 相對低點淘金與金字塔分批建倉決策引擎 (精準打擊強化版)
專注於：
1. 指標底背離偵測 (Bullish Divergence: MACD 柱狀圖 / RSI 底底高)
2. 多日反轉 K 線型態組合 (破底翻長紅吞噬 / 晨星 / W底二次探底打樁)
3. 斐波那契黃金分割率 (Fibonacci Retracement 0.500~0.618 黃金口袋區)
4. 多時框趨勢保護 (季線 60MA / 半年線 120MA 守穩)
5. 布林通道下軌極值 (%B <= 0.15~0.25)
6. 成交量窒息量籌碼沉澱 (Volume Dry-up < 0.65)
7. 黃金精準打擊星等評級 (1 ~ 5 星級量表)
8. 金字塔三段分批建倉階梯 (首批試單 30% / 右側加碼 40% / 順勢加滿 30% / 停損點)
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from etf_analytics import ETFPerformance, calculate_all_performances
from etf_fetcher import fetch_all_tw_etfs


@dataclass
class ETFDipAdvisory:
    perf: ETFPerformance
    dip_quality_score: float      # 相對低點淘金評分 (0 ~ 100)
    signal: str                   # 👑 皇冠級精準打擊 / 💎 頂級黃金買點 / 🎯 拉回守穩佈局 / ⏸️ 觀望等待打底 / ⚠️ 偏高不宜建倉
    action: str                   # 建議具體操作
    golden_stars: int             # 精準打擊星等 (1 ~ 5 星)
    star_badge: str               # 星等徽章 (👑 5星 皇冠級精準打擊 / 💎 4星 頂級黃金買點 / 🎯 3星 高勝率佈局 / ⚡ 2星 短線超跌試單 / ⚠️ 1星 觀望防守)
    divergence_type: str          # 底背離偵測 (RSI / MACD 底底高)
    reversal_pattern: str         # K線反轉型態 (破底翻吞噬 / W底 / 晨星 / 探底Pinbar)
    fib_0618: float               # 斐波那契 0.618 黃金回撤支撐價
    fib_0500: float               # 斐波那契 0.500 回撤支撐價
    is_fib_confluence: bool       # 是否落於黃金回撤口袋區 (0.500~0.618)
    trend_alignment: str          # 長線保護趨勢 (季線/半年線支撐狀態)
    stage1_price: float           # 第 1 批：左側試單價 (30% 水位)
    stage2_price: float           # 第 2 批：右側確認加碼價 (40% 水位)
    stage3_price: float           # 第 3 批：順勢加滿價 (30% 水位)
    stop_loss_price: float        # 嚴格防守停損價
    target_price: float           # 波段目標價
    percent_b: float              # 布林通道 %B (0.0~1.0, <0.20 為超跌黃金右腳)
    vol_ratio_20: float           # 成交量 / 20日均量 (小於 0.65 為窒息量)
    lower_shadow_ratio: float     # K線下影線比例 (%)
    bb_lower: float               # 布林通道下軌價
    bb_upper: float               # 布林通道上軌價
    margin_maint_ratio: float     # 大盤推估融資維持率 (%)
    margin_status: str            # 大盤融資狀態 (🩸 融資斷頭黃金底 / ⚠️ 融資警戒追繳區 / 🛡️ 融資健康水位)
    etf_margin_change: int        # 個別 ETF 當日融資增減 (張，負數代表融資減肥籌碼沉澱)
    vix_value: float              # 恐慌指數 VIX 數值
    vix_status: str               # 恐慌指數狀態 (👑 VIX恐慌見頂回落 / 😱 VIX極度恐慌飆高 / ⚖️ VIX常態震盪)
    etf_nav: float = 0.0          # ETF 官方預估淨值 (元)
    premium_discount_rate: float = 0.0 # ETF 折溢價率 (%)
    nav_status: str = ""          # 折溢價狀態 (💎 實質折價超值 / ⚠️ 嚴重溢價警戒 / ⚖️ 常態合理)
    foreign_futures_net_oi: int = 0    # 外資大台指期淨未平倉留倉口數
    foreign_futures_oi_change: int = 0 # 外資單日空單增減 (大額回補 > 3000口為軋空信號)
    taifex_pc_ratio: float = 0.0       # 台指選擇權 Put/Call Ratio (%)
    taifex_pc_status: str = ""         # 選擇權籌碼多空評估 (👑 極度超跌 / ⚡ 空方耗竭 / ⚖️ 常態)
    reasons: list[str] = field(default_factory=list) # 低點研判核心依據條列


def detect_bullish_divergence(df: pd.DataFrame) -> tuple[str, int]:
    """
    偵測指標底背離 (Bullish Divergence)：
    價格創近期新低 (或接近前低)，但 RSI 或 MACD 柱狀圖卻不破底、甚至底底高。
    代表空方下殺動能已耗盡、主力隱性吃貨。
    """
    if len(df) < 25:
        return "無背離", 0

    close_series = df["Close"]
    low_series = df["Low"]

    # 1. 計算 RSI(14)
    delta = close_series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))

    # 2. 計算 MACD(12,26,9) 柱狀圖
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_osc = (dif - dea) * 2

    # 觀察最近 5 天之最低點 (T1) vs 前期 6~22 天之最低點 (T0)
    rec_lows = low_series.iloc[-5:]
    t1_pos = rec_lows.idxmin()
    p1 = float(low_series.loc[t1_pos])
    rsi1 = float(rsi_series.loc[t1_pos])
    macd1 = float(macd_osc.loc[t1_pos])

    prior_lows = low_series.iloc[-22:-5]
    if len(prior_lows) < 5:
        return "無背離", 0
    t0_pos = prior_lows.idxmin()
    p0 = float(low_series.loc[t0_pos])
    rsi0 = float(rsi_series.loc[t0_pos])
    macd0 = float(macd_osc.loc[t0_pos])

    # 底背離判讀條件：
    # 價格跌破前低或與前低相當 (p1 <= p0 * 1.01)
    # 但 RSI 底底高 (rsi1 >= rsi0 + 2.5) 且處於超賣/偏低位階 (rsi1 <= 48)
    has_rsi_div = (p1 <= p0 * 1.01) and (rsi1 >= rsi0 + 2.5) and (rsi1 <= 48)
    # 或 MACD 柱狀圖底底高 (綠柱顯著縮小或由負翻正)
    has_macd_div = (p1 <= p0 * 1.01) and (macd1 > macd0 + 0.05) and (macd1 < 0.2)

    if has_rsi_div and has_macd_div:
        return "⚡ RSI + MACD 雙重底背離 (極致動能耗竭)", 25
    elif has_rsi_div:
        return "⚡ RSI 低檔底背離 (主力隱性吃貨)", 18
    elif has_macd_div:
        return "⚡ MACD 柱狀圖底背離 (殺盤力道枯竭)", 14
    return "無背離", 0


def detect_candlestick_reversal(df: pd.DataFrame, lower_shadow_ratio: float) -> tuple[str, int]:
    """
    偵測多日複合反轉 K 線型態：
    1. 破底翻長紅吞噬 (Bullish Engulfing)
    2. 晨星型態 (Morning Star)
    3. W 底二次探底守穩 (Double Bottom)
    4. 長下影線探底打樁 (Pinbar)
    """
    if len(df) < 5:
        return "一般K線", 0

    c = float(df["Close"].iloc[-1])
    o = float(df["Open"].iloc[-1])
    h = float(df["High"].iloc[-1])
    l = float(df["Low"].iloc[-1])

    c_prev = float(df["Close"].iloc[-2])
    o_prev = float(df["Open"].iloc[-2])
    h_prev = float(df["High"].iloc[-2])
    l_prev = float(df["Low"].iloc[-2])

    body_now = c - o
    body_prev = c_prev - o_prev

    # 1. 破底翻長紅吞噬 (今日長紅完全包覆昨日黑K)
    is_engulfing = (body_prev < 0) and (body_now > 0) and (c >= o_prev) and (o <= c_prev * 1.002) and (body_now >= abs(body_prev) * 0.9)

    # 2. 晨星 (Morning Star) 3日組合
    is_morning_star = False
    if len(df) >= 3:
        c_2 = float(df["Close"].iloc[-3])
        o_2 = float(df["Open"].iloc[-3])
        body_2 = c_2 - o_2
        if (body_2 < 0) and (abs(body_prev) < abs(body_2) * 0.5) and (body_now > 0) and (c >= (c_2 + o_2) / 2):
            is_morning_star = True

    # 3. W 底二次探底守穩 (Double Bottom with Higher Low)
    is_double_bottom = False
    prior_window = df["Low"].iloc[-20:-3]
    if len(prior_window) >= 5:
        prior_min = float(prior_window.min())
        # 本次探底與前波低點相差 within 1.5%，且今日收紅守穩
        if abs(l - prior_min) / (prior_min + 1e-9) <= 0.018 and c >= o and c > l:
            is_double_bottom = True

    if is_engulfing:
        return "🔥 破底翻長紅吞噬 (多方強勢反轉確立)", 22
    elif is_morning_star:
        return "🌟 經典晨星反轉 (空翻多訊號啟動)", 18
    elif is_double_bottom:
        return "👑 W底二次探底守穩 (築底黃金右腳)", 16
    elif lower_shadow_ratio >= 38.0:
        return "🔨 長下影線探底打樁 (低接買盤積極)", 12
    elif lower_shadow_ratio >= 22.0:
        return "🔨 下影線回測守穩", 6
    return "無特殊反轉K線", 0


def calculate_fibonacci_retracement(df: pd.DataFrame, curr_price: float) -> tuple[float, float, bool, str, int]:
    """
    計算過去 60~75 日波段之斐波那契黃金分割率：
    0.382 / 0.500 / 0.618 黃金口袋區 (Golden Pocket)
    """
    if len(df) < 25:
        return round(curr_price * 0.96, 2), round(curr_price * 0.94, 2), False, "波段數據累積中", 0

    window = min(len(df), 75)
    sub_df = df.iloc[-window:]
    high_val = float(sub_df["High"].max())
    low_val = float(sub_df["Low"].min())
    diff = high_val - low_val

    if diff <= 0.04 * high_val:
        return round(curr_price * 0.96, 2), round(curr_price * 0.94, 2), False, "近月窄幅整理", 0

    fib_0500 = round(high_val - diff * 0.500, 2)
    fib_0618 = round(high_val - diff * 0.618, 2)
    fib_0382 = round(high_val - diff * 0.382, 2)

    # 黃金口袋區判定：現價在 0.500 ~ 0.618 回撤區間 (+- 1.5% 容許度)
    is_in_golden_pocket = (curr_price >= fib_0618 * 0.985) and (curr_price <= fib_0500 * 1.018)

    if is_in_golden_pocket:
        desc = f"🎯【斐波那契黃金口袋】回撤至 0.500~0.618 黃金分割位 ({fib_0618:.2f} ~ {fib_0500:.2f})"
        return fib_0500, fib_0618, True, desc, 16
    elif curr_price >= fib_0382 * 0.99:
        desc = f"波段回撤 0.382 強勢位 ({fib_0382:.2f})"
        return fib_0500, fib_0618, False, desc, 6
    elif curr_price < fib_0618 * 0.985:
        desc = f"回撤跌破 0.618 斐波位 ({fib_0618:.2f})"
        return fib_0500, fib_0618, False, desc, 2
    else:
        desc = f"回撤接近 0.500 支撐位 ({fib_0500:.2f})"
        return fib_0500, fib_0618, False, desc, 8


def check_trend_protection(df: pd.DataFrame, curr_price: float) -> tuple[str, int]:
    """
    多時框均線保護分析：
    檢查是否守穩季線 (60MA 生命線) 或半年線 (120MA 大底支撐)
    長線保護短線，確保不是在空頭大主跌段接刀
    """
    n = len(df)
    sma60 = float(df["Close"].rolling(60).mean().iloc[-1]) if n >= 60 else None
    sma120 = float(df["Close"].rolling(120).mean().iloc[-1]) if n >= 120 else None

    if sma60 and curr_price >= sma60 * 0.99:
        sma60_prev = float(df["Close"].rolling(60).mean().iloc[-10]) if n >= 70 else sma60
        is_sma60_up = sma60 >= sma60_prev
        if is_sma60_up:
            return "🛡️ 季線 (60MA) 上揚多頭守穩 (長線保護短線)", 14
        return "🛡️ 守穩季線 (60MA) 關鍵生命線", 8
    elif sma120 and curr_price >= sma120 * 0.99:
        return "🛡️ 半年線 (120MA) 關鍵大支撐守穩", 10
    elif sma60 and curr_price < sma60 * 0.94:
        return "⚠️ 跌破季線生命線 (長線偏空格局)", -15
    return "一般均線位階", 0


def evaluate_etf_dip(p: ETFPerformance, etf_df: pd.DataFrame, benchmark_df: pd.DataFrame = None, margin_data: dict = None, vix_data: dict = None, nav_info: dict = None, deriv_data: dict = None) -> ETFDipAdvisory:
    """
    計算單檔標的之相對低點特徵、淘金評分、多維共振、融資維持率、VIX恐慌指數、ETF折溢價率與外資期貨/選擇權共振
    """
    reasons = []
    score = 42.0  # 基準分數

    is_leveraged_2x = "正2" in p.category or p.ticker.endswith("L.TW")
    is_active_etf = "主動" in p.category or "A.TW" in p.ticker

    # 1. 取得歷史數據與布林通道計算
    df = etf_df.copy().sort_index()
    n = len(df)
    curr_price = p.current_price
    bias_20 = getattr(p, "bias_20", round(((curr_price - p.sma_20) / (p.sma_20 + 1e-9)) * 100.0, 2))

    # 布林通道 (20MA, 2 std)
    if n >= 20:
        roll_mean = df["Close"].rolling(20).mean()
        roll_std = df["Close"].rolling(20).std()
        bb_upper = float((roll_mean + 2 * roll_std).iloc[-1])
        bb_lower = float((roll_mean - 2 * roll_std).iloc[-1])
        bb_width = bb_upper - bb_lower
        percent_b = float((curr_price - bb_lower) / (bb_width + 1e-9))
    else:
        bb_upper = curr_price * 1.05
        bb_lower = curr_price * 0.95
        percent_b = 0.50

    # 2. 成交量窒息量計算 (Volume Dry-up)
    if "Volume" in df.columns and n >= 20:
        vma20 = float(df["Volume"].rolling(20).mean().iloc[-1])
        curr_vol = float(df["Volume"].iloc[-1])
        vol_ratio_20 = round(curr_vol / (vma20 + 1e-9), 2)
    else:
        vol_ratio_20 = 1.0

    # 3. K 線下影線收腳特徵 (Lower Shadow Pinbar)
    latest_row = df.iloc[-1]
    candle_open = float(latest_row.get("Open", curr_price))
    candle_high = float(latest_row.get("High", curr_price))
    candle_low = float(latest_row.get("Low", curr_price))
    candle_range = max(candle_high - candle_low, 1e-4)
    body_bottom = min(candle_open, curr_price)
    lower_shadow_ratio = round(((body_bottom - candle_low) / candle_range) * 100.0, 1)

    # ───────────────────────────────────────────────────────────
    # A. 布林通道下軌極值判定 (%B)
    # ───────────────────────────────────────────────────────────
    if percent_b <= 0.15:
        score += 24
        reasons.append(f"💎【布林極端超跌】價格觸及布林下軌 (%B: {percent_b:.2f})，常態分佈統計超跌黃金右腳浮現！")
    elif percent_b <= 0.30:
        score += 15
        reasons.append(f"💎【布林偏低安全區】處於布林中下軌偏低位階 (%B: {percent_b:.2f})，下檔空間有限。")
    elif percent_b >= 0.85:
        score -= 30
        reasons.append(f"⚠️【布林上軌過熱】價格逼近布林通道上軌 (%B: {percent_b:.2f})，絕非相對低點，嚴禁追價！")
    elif percent_b >= 0.70:
        score -= 15
        reasons.append(f"⚠️【布林偏高位階】處於布林中上軌發散區 (%B: {percent_b:.2f})，追價勝率低。")

    # ───────────────────────────────────────────────────────────
    # B. 月線乖離與關鍵支撐守穩
    # ───────────────────────────────────────────────────────────
    if 0.0 <= bias_20 <= 2.2 and curr_price >= p.sma_20 * 0.995:
        score += 20
        reasons.append(f"🎯【多頭月線守穩】拉回 20MA 月線關鍵支撐獲得撐盤 (正乖離僅 {bias_20:+.2f}%)，盈虧比極佳。")
    elif bias_20 <= -4.0:
        score += 16
        reasons.append(f"💎【均線負乖離過大】月線負乖離達 {bias_20:+.2f}%，短線醞釀均值回歸報復性反彈。")
    elif bias_20 >= 4.0:
        score -= 22
        reasons.append(f"⚠️【正乖離偏高】月線正乖離過大 ({bias_20:+.2f}%)，短線隨時面臨回檔修乖離。")

    # ───────────────────────────────────────────────────────────
    # C. 成交量窒息量 (籌碼沉澱 vs 爆量下殺倒貨)
    # ───────────────────────────────────────────────────────────
    is_falling_knife = False
    if vol_ratio_20 >= 1.5 and p.pct_change_1d < -0.5 and lower_shadow_ratio < 15.0:
        is_falling_knife = True
        score -= 35
        reasons.insert(0, f"🚨【帶量下殺倒貨風險】今日光頭收低伴隨爆量 ({vol_ratio_20*100:.0f}% 均量)，空方賣壓劇烈尚未沉澱，嚴禁接刀！")
    elif vol_ratio_20 <= 0.60:
        score += 18
        reasons.append(f"🧊【極致窒息量沉澱】成交量縮至 20 日均量 {vol_ratio_20*100:.0f}%，市場浮額清洗完畢、賣壓枯竭！")
    elif vol_ratio_20 <= 0.80:
        score += 10
        reasons.append(f"🧊【回檔良性量縮】成交量為 20 日均量 {vol_ratio_20*100:.0f}%，呈現無量回測整理。")
    elif vol_ratio_20 >= 1.6 and p.pct_change_1d < -0.8:
        score -= 20
        reasons.append(f"⚠️【帶量下殺倒貨】下跌伴隨顯著出量 ({vol_ratio_20:.1f}倍均量)，籌碼尚未沉澱。")

    # ───────────────────────────────────────────────────────────
    # D. 👑 精準打擊 1：指標底背離偵測 (Bullish Divergence)
    # ───────────────────────────────────────────────────────────
    div_desc, div_score = detect_bullish_divergence(df)
    if div_score > 0:
        score += div_score
        reasons.insert(0, f"👑【黃金底背離】{div_desc}")

    # ───────────────────────────────────────────────────────────
    # E. 👑 精準打擊 2：多日複合反轉 K 線型態 (Engulfing / Morning Star / W-Bottom)
    # ───────────────────────────────────────────────────────────
    pattern_desc, pattern_score = detect_candlestick_reversal(df, lower_shadow_ratio)
    if pattern_score > 0:
        score += pattern_score
        reasons.append(f"📈【反轉型態】{pattern_desc}")

    # ───────────────────────────────────────────────────────────
    # F. 👑 精準打擊 3：斐波那契黃金分割率 (Fibonacci 0.500~0.618 Pocket)
    # ───────────────────────────────────────────────────────────
    fib_0500, fib_0618, is_fib_confluence, fib_desc, fib_score = calculate_fibonacci_retracement(df, curr_price)
    if fib_score > 0:
        score += fib_score
        reasons.append(fib_desc)

    # ───────────────────────────────────────────────────────────
    # G. 👑 精準打擊 4：長天期趨勢保護 (季線/半年線支撐)
    # ───────────────────────────────────────────────────────────
    trend_desc, trend_score = check_trend_protection(df, curr_price)
    score += trend_score
    if trend_score > 0:
        reasons.append(trend_desc)
    elif trend_score < 0:
        reasons.append(trend_desc)

    # ───────────────────────────────────────────────────────────
    # H. KD & RSI 動能轉折
    # ───────────────────────────────────────────────────────────
    if p.k_9 > p.d_9 and p.k_9 <= 50:
        score += 10
        reasons.append(f"⚡【KD低檔黃金交叉】KD 於健康低位翻揚 (K:{p.k_9:.1f} > D:{p.d_9:.1f})，轉折攻擊動能啟動。")
    elif p.k_9 < p.d_9 and p.k_9 >= 70:
        score -= 10
        reasons.append(f"⚠️【KD高檔死亡交叉】KD 高檔修正 (K:{p.k_9:.1f} < D:{p.d_9:.1f})。")

    if p.rsi_14 <= 32:
        score += 10
        reasons.append(f"💎【RSI超跌區】RSI(14) 降至 {p.rsi_14:.1f}，技術面處於超賣超跌反彈區。")
    elif p.rsi_14 >= 70:
        score -= 15
        reasons.append(f"⚠️【RSI超買過熱】RSI(14) 達 {p.rsi_14:.1f}，高檔過熱。")

    # ───────────────────────────────────────────────────────────
    # I. 主動型經理人勝率 & 正2專屬防護
    # ───────────────────────────────────────────────────────────
    if is_active_etf and p.manager_win_rate >= 52.0:
        score += 8
        reasons.append(f"🎖️【經理人勝率高】日戰勝大盤勝率達 {p.manager_win_rate:.1f}%，抗跌與選股超額報酬能力佳。")

    if is_leveraged_2x:
        if percent_b > 0.60 or bias_20 > 3.0:
            score -= 15
        if abs(p.return_1m) < 3.0 and p.volatility_ann > 25.0:
            score -= 10
            reasons.append("⚠️【正2警惕震盪耗損】盤整無趨勢易受每日重設耗損，建議等待右側帶量突破再行佈局。")

    # ───────────────────────────────────────────────────────────
    # J. 🩸 融資融券籌碼清洗分析 (大盤維持率 & 個別 ETF 融資增減)
    # ───────────────────────────────────────────────────────────
    margin_maint_ratio = 165.0
    margin_status = "🛡️ 融資健康水位"
    etf_margin_change = 0

    if margin_data:
        margin_maint_ratio = float(margin_data.get("est_maint_ratio", 165.0))
        m_chg_billion = float(margin_data.get("margin_total_change_billion", 0.0))

        if margin_maint_ratio <= 145.0 or m_chg_billion <= -30.0:
            margin_status = "🩸 融資斷頭黃金底"
            score += 20
            reasons.insert(0, f"🩸【融資斷頭清洗】大盤融資維持率降至 {margin_maint_ratio:.1f}% 瀕臨斷頭線(單日融資減肥 {m_chg_billion:+.1f}億)，散戶恐慌砍倉籌碼落入法人手中，歷史大底浮現！")
        elif margin_maint_ratio <= 155.0:
            margin_status = "⚠️ 融資警戒追繳區"
            score += 8
            reasons.append(f"⚠️【融資警戒追繳】大盤融資維持率降至 {margin_maint_ratio:.1f}%，短線融資浮額持續清洗。")
        else:
            margin_status = "🛡️ 融資健康水位"

        # 個別 ETF 融資增減分析
        clean_code = p.ticker.replace(".TW", "").replace(".TWO", "").strip()
        etf_m_info = margin_data.get("etf_margins", {}).get(clean_code, {})
        if etf_m_info:
            etf_margin_change = etf_m_info.get("margin_change_sheets", 0)
            if etf_margin_change < 0 and percent_b <= 0.35:
                score += 10
                reasons.append(f"🧹【散戶融資退場】今日融資減肥 {abs(etf_margin_change):,} 張，低檔散戶認賠停損，籌碼浮額洗淨！")
            elif etf_margin_change > 1500 and p.pct_change_1d < -0.8:
                score -= 10
                reasons.append(f"⚠️【散戶融資逆勢加碼】今日融資增加 {etf_margin_change:,} 張，散戶低檔持續攤平，籌碼尚未沉澱。")

    # ───────────────────────────────────────────────────────────
    # K. 😱 恐慌指數 VIX 情緒反轉分析 (別人恐懼我貪婪)
    # ───────────────────────────────────────────────────────────
    vix_val = 19.5
    vix_status = "⚖️ VIX常態震盪"

    if vix_data:
        vix_val = float(vix_data.get("curr_vix", 19.5))
        is_peak = vix_data.get("is_peak_reversal", False)
        is_panic = vix_data.get("is_extreme_panic", False)

        if is_peak and percent_b <= 0.40:
            vix_status = "👑 VIX恐慌見頂回落"
            score += 18
            reasons.insert(0, f"👑【VIX恐慌見頂反轉】恐慌指數 (VIX: {vix_val:.1f}) 衝高後長上影回落，極端恐慌情緒宣洩完畢，絕佳右側買點！")
        elif is_panic:
            vix_status = "😱 VIX極度恐慌飆高"
            score += 10
            reasons.append(f"😱【VIX極度恐慌】恐慌指數飆升至 {vix_val:.1f}，市場非理性拋售，醞釀報復性反彈。")
        else:
            vix_status = "⚖️ VIX常態震盪"

    # ───────────────────────────────────────────────────────────
    # L. 💎 ETF 實質折溢價率 (NAV Premium / Discount Rate Filter)
    # ───────────────────────────────────────────────────────────
    etf_nav = curr_price
    prem_rate = 0.0
    nav_status = "⚖️ 常態合理 (0.00%)"
    is_severe_premium = False

    if nav_info:
        etf_nav = float(nav_info.get("est_nav", curr_price))
        prem_rate = float(nav_info.get("premium_discount_rate", 0.0))
        nav_status = nav_info.get("nav_status", "⚖️ 常態合理")
        is_severe_premium = nav_info.get("is_severe_premium", False)

        if prem_rate < -0.10:
            score += 10
            reasons.append(f"💎【實質折價超值】折價 {prem_rate:.2f}% (市價低於淨值)，買在超值折價安全邊際！")
        elif prem_rate > 0.80:
            score -= 25
            reasons.insert(0, f"⚠️【高溢價警戒】溢價達 +{prem_rate:.2f}%，造市商將套利壓盤倒貨，暫停追高！")
        elif prem_rate > 0.40:
            score -= 6

    # ───────────────────────────────────────────────────────────
    # M. 🎯 外資期貨淨空單與選擇權 Put/Call Ratio (Derivatives Squeeze)
    # ───────────────────────────────────────────────────────────
    tx_foreign_net_oi = 0
    tx_foreign_oi_change = 0
    taifex_pc_ratio = 95.0
    taifex_pc_status = "⚖️ 選擇權常態"

    if deriv_data:
        tx_foreign_net_oi = deriv_data.get("tx_foreign_net_oi", 0)
        tx_foreign_oi_change = deriv_data.get("tx_foreign_oi_change", 0)
        taifex_pc_ratio = float(deriv_data.get("pc_ratio", 95.0))
        taifex_pc_status = deriv_data.get("pc_status", "常態")

        # 選擇權極度超跌轉折
        if taifex_pc_ratio <= 70.0:
            score += 15
            reasons.insert(0, f"👑【選擇權極度超跌】台指選擇權 P/C Ratio 僅 {taifex_pc_ratio:.1f}% (≤70%)，莊家空方極限防守，反轉爆發機率極高！")
        elif taifex_pc_ratio <= 78.0:
            score += 8
            reasons.append(f"⚡【選擇權空方耗竭】P/C Ratio 降至 {taifex_pc_ratio:.1f}%，低檔籌碼沉澱具軋空彈性。")
        elif taifex_pc_ratio >= 115.0:
            score += 6
            reasons.append(f"🔥【選擇權偏多主控】P/C Ratio 達 {taifex_pc_ratio:.1f}%，多方支撐力道扎實。")

        # 外資期貨大額回補
        if deriv_data.get("is_short_squeeze", False) or tx_foreign_oi_change >= 3000:
            score += 14
            reasons.insert(0, f"🚀【外資空單大額回補】外資單日大補空單 +{tx_foreign_oi_change:,} 口，籌碼由空翻多具軋空動能！")
        elif tx_foreign_net_oi <= -35000 and tx_foreign_oi_change < -1500:
            score -= 8
            reasons.append(f"⚠️【外資期貨空單壓盤】淨空單高達 {abs(tx_foreign_net_oi):,} 口且持續加空，提防法人壓盤結算。")

    score = float(max(min(score, 100), 0))

    # ───────────────────────────────────────────────────────────
    # N. 👑 精準打擊星等評定 (Golden Star Rating: 1~5 星)
    # ───────────────────────────────────────────────────────────
    has_top_reversal = (div_score > 0 or pattern_score >= 16 or "斷頭" in margin_status or "見頂" in vix_status or taifex_pc_ratio <= 75.0)
    if is_falling_knife or score < 38 or percent_b >= 0.75:
        golden_stars = 1
        star_badge = "⚠️ 1星 (觀望防守)"
    elif is_severe_premium:
        # 高溢價嚴格限制星等上限
        golden_stars = min(2, int(score // 20))
        star_badge = "⚠️ 2星 (高溢價警戒限制)"
        reasons.insert(0, f"⚠️【高溢價強制降星】溢價 +{prem_rate:.2f}% 過高，嚴防造市商收斂打回原形，限制評級最高 2 星！")
    elif score >= 75 and has_top_reversal and percent_b <= 0.38:
        golden_stars = 5
        star_badge = "👑 5星 (皇冠級精準打擊)"
    elif score >= 62 and (has_top_reversal or is_fib_confluence or percent_b <= 0.25):
        golden_stars = 4
        star_badge = "💎 4星 (頂級黃金買點)"
    elif score >= 50:
        golden_stars = 3
        star_badge = "🎯 3星 (高勝率佈局)"
    elif score >= 38:
        golden_stars = 2
        star_badge = "⚡ 2星 (短線超跌試單)"
    else:
        golden_stars = 1
        star_badge = "⚠️ 1星 (觀望防守)"

    # ───────────────────────────────────────────────────────────
    # O. 訊號判定
    # ───────────────────────────────────────────────────────────
    if is_falling_knife:
        signal = "🚨 破位出量觀望 (Falling Knife)"
        action = "爆量收低賣壓劇烈 / 嚴禁盲目接刀"
    elif is_severe_premium:
        signal = "⚠️ 高溢價避開 (Premium Risk)"
        action = "市價嚴重高於淨值 / 暫停買進"
    elif golden_stars == 5:
        signal = "👑 皇冠級精準打擊 (Five-Star Dip)"
        action = "多維黃金共振！強烈建議啟動建倉 (首批試單 35%)"
    elif golden_stars == 4 or (score >= 68 and percent_b <= 0.35):
        signal = "💎 頂級黃金買點 (Prime Dip)"
        action = "啟動金字塔分批建倉：首批試單 30%"
    elif golden_stars == 3 or score >= 52:
        signal = "🎯 拉回守穩佈局 (Pullback Buy)"
        action = "逢低分批佈局 / 守穩加碼"
    elif score <= 35 or percent_b >= 0.75:
        signal = "⚠️ 偏高不宜建倉 (Avoid / Trim)"
        action = "位階偏高或尚未止跌 / 嚴禁追價"
    else:
        signal = "⏸️ 觀望等待打底 (Watch)"
        action = "區間震盪整理 / 靜待出量收腳"

    # ───────────────────────────────────────────────────────────
    # P. 斐波那契融合之「金字塔三段建倉點位」
    # ───────────────────────────────────────────────────────────
    atr = p.atr_14 if p.atr_14 > 0 else max(curr_price * 0.02, 0.1)

    if curr_price >= p.sma_20 * 0.99:
        # 多頭拉回型：月線有撐
        stage1 = round(min(curr_price, max(p.sma_20 * 0.995, curr_price * 0.99)), 2)
        stage2 = round(max(stage1 + 0.04, p.sma_5 * 1.003, curr_price * 1.01), 2)
        stage3 = round(max(stage2 + 0.05, curr_price + 1.2 * atr), 2)
        stop_loss = round(min(stage1 - 0.05, p.sma_20 * 0.985, stage1 - 1.2 * atr), 2)
        target = round(max(stage3 + 0.1, bb_upper, curr_price + 2.0 * atr), 2)
    else:
        # 超跌負乖離型：深水區撈底
        if is_fib_confluence:
            stage1 = round(min(curr_price, max(fib_0618, bb_lower)), 2)
        else:
            stage1 = round(min(curr_price, max(curr_price * 0.995, bb_lower)), 2)
        stage2 = round(max(stage1 + 0.04, p.sma_5 * 1.002, curr_price * 1.015), 2)
        stage3 = round(max(stage2 + 0.05, p.sma_20 * 1.002, curr_price + 1.2 * atr), 2)
        stop_loss = round(min(stage1 - 0.05, curr_price - 1.0 * atr, bb_lower * 0.985), 2)
        target = round(max(stage3 + 0.1, bb_upper, curr_price + 2.2 * atr), 2)

    return ETFDipAdvisory(
        perf=p,
        dip_quality_score=round(score, 1),
        signal=signal,
        action=action,
        golden_stars=golden_stars,
        star_badge=star_badge,
        divergence_type=div_desc,
        reversal_pattern=pattern_desc,
        fib_0618=fib_0618,
        fib_0500=fib_0500,
        is_fib_confluence=is_fib_confluence,
        trend_alignment=trend_desc,
        stage1_price=stage1,
        stage2_price=stage2,
        stage3_price=stage3,
        stop_loss_price=stop_loss,
        target_price=target,
        percent_b=round(percent_b, 2),
        vol_ratio_20=vol_ratio_20,
        lower_shadow_ratio=lower_shadow_ratio,
        bb_lower=round(bb_lower, 2),
        bb_upper=round(bb_upper, 2),
        margin_maint_ratio=margin_maint_ratio,
        margin_status=margin_status,
        etf_margin_change=etf_margin_change,
        vix_value=round(vix_val, 2),
        vix_status=vix_status,
        etf_nav=round(etf_nav, 2),
        premium_discount_rate=round(prem_rate, 2),
        nav_status=nav_status,
        foreign_futures_net_oi=tx_foreign_net_oi,
        foreign_futures_oi_change=tx_foreign_oi_change,
        taifex_pc_ratio=round(taifex_pc_ratio, 2),
        taifex_pc_status=taifex_pc_status,
        reasons=reasons
    )


def fetch_vix_status_data() -> dict:
    """獲取最新 VIX 報價與恐慌反轉信號"""
    try:
        import yfinance as yf
        vix_df = yf.download("^VIX", period="1mo", interval="1d", progress=False)
        c_series = vix_df["Close"].squeeze()
        h_series = vix_df["High"].squeeze()
        curr_vix = float(c_series.iloc[-1])
        prev_vix = float(c_series.iloc[-2]) if len(c_series) >= 2 else curr_vix
        high_vix = float(h_series.iloc[-1]) if len(h_series) >= 1 else curr_vix
        chg_vix = curr_vix - prev_vix

        is_panic = curr_vix >= 25.0
        is_peak = (high_vix >= 21.0 or prev_vix >= 21.0) and (curr_vix < high_vix * 0.94 or chg_vix < -0.8)
        return {
            "curr_vix": curr_vix,
            "prev_vix": prev_vix,
            "high_vix": high_vix,
            "chg_vix": chg_vix,
            "is_extreme_panic": is_panic,
            "is_peak_reversal": is_peak
        }
    except Exception:
        return {"curr_vix": 19.5, "prev_vix": 19.5, "high_vix": 21.0, "chg_vix": 0.0, "is_extreme_panic": False, "is_peak_reversal": False}


def evaluate_all_etfs_dip(force_reload: bool = False) -> list[ETFDipAdvisory]:
    """獲取全部標的之相對低點淘金評估列表（含官方融資融券、VIX恐慌、折溢價率與期貨選擇權共振）"""
    perfs = calculate_all_performances(force_reload=force_reload)
    data_dict = fetch_all_tw_etfs(period="1y", force_reload=force_reload)
    bench_df = data_dict.get("^TWII")

    # 1. 抓取真實大盤與個股融資融券資料
    margin_data = {}
    try:
        from chip_fetcher import fetch_twse_margin_single_day, calculate_estimated_margin_maintenance_ratio
        m_info = fetch_twse_margin_single_day()
        if m_info:
            margin_data = m_info
            if bench_df is not None and "Close" in bench_df.columns:
                margin_data["est_maint_ratio"] = calculate_estimated_margin_maintenance_ratio(bench_df["Close"])
    except Exception:
        margin_data = {}

    # 2. 抓取最新 VIX 恐慌指標狀態
    vix_data = fetch_vix_status_data()

    # 3. 抓取全市場 ETF 官方預估淨值與折溢價率 (TWSE MIS)
    nav_all_map = {}
    try:
        from chip_fetcher import fetch_twse_etf_nav_all
        nav_all_map = fetch_twse_etf_nav_all()
    except Exception:
        nav_all_map = {}

    # 4. 抓取期貨外資留倉與選擇權 Put/Call Ratio (TAIFEX)
    deriv_data = {}
    try:
        from chip_fetcher import fetch_taifex_latest_derivatives
        deriv_data = fetch_taifex_latest_derivatives()
    except Exception:
        deriv_data = {}

    advisories = []
    for p in perfs:
        df = data_dict.get(p.ticker)
        clean_code = p.ticker.replace(".TW", "").replace(".TWO", "").strip()
        nav_info = nav_all_map.get(clean_code)

        if df is not None and len(df) >= 20:
            adv = evaluate_etf_dip(p, df, bench_df, margin_data=margin_data, vix_data=vix_data, nav_info=nav_info, deriv_data=deriv_data)
            advisories.append(adv)
        else:
            dummy_df = pd.DataFrame({
                "Close": [p.current_price]*25,
                "High": [p.current_price]*25,
                "Low": [p.current_price]*25,
                "Open": [p.current_price]*25,
                "Volume": [p.volume]*25
            })
            adv = evaluate_etf_dip(p, dummy_df, bench_df, margin_data=margin_data, vix_data=vix_data, nav_info=nav_info, deriv_data=deriv_data)
            advisories.append(adv)

    # 依「低點淘金評分」與「黃金星等」由高至低排序
    advisories.sort(key=lambda x: (x.golden_stars, x.dip_quality_score), reverse=True)
    return advisories


def get_top_dip_picks(advisories: list[ETFDipAdvisory], limit: int = 3) -> list[ETFDipAdvisory]:
    """
    量化精選「精準打擊黃金買點」前三檔：
    1. 優先挑選具有 4~5 星級【皇冠級精準打擊 / 頂級黃金買點】之標的
    2. 優先挑選具備【底背離】或【反轉K線吞噬】之共振標的
    3. 布林 %B <= 0.45 (排除中高軌過熱標的)
    """
    # 先挑選 4~5 星且低位階
    five_star_candidates = [
        a for a in advisories
        if a.golden_stars >= 4 and a.percent_b <= 0.48
    ]

    def dip_rank_key(a: ETFDipAdvisory) -> float:
        # 星等權重 + 品質分 + 經理人勝率權重 - 布林位階懲罰
        div_bonus = 20.0 if "背離" in a.divergence_type and "無" not in a.divergence_type else 0.0
        pat_bonus = 15.0 if "吞噬" in a.reversal_pattern or "晨星" in a.reversal_pattern or "W底" in a.reversal_pattern else 0.0
        return (a.golden_stars * 30.0) + a.dip_quality_score + div_bonus + pat_bonus + (a.perf.manager_win_rate * 0.25) - (a.percent_b * 20.0)

    if len(five_star_candidates) >= limit:
        return sorted(five_star_candidates, key=dip_rank_key, reverse=True)[:limit]

    # 若 4~5 星不足，加入 3 星候選
    valid_candidates = [
        a for a in advisories
        if a.golden_stars >= 3 and a.percent_b <= 0.48
    ]

    if len(valid_candidates) >= limit:
        return sorted(valid_candidates, key=dip_rank_key, reverse=True)[:limit]
    elif valid_candidates:
        remaining = [a for a in advisories if a not in valid_candidates and "偏高" not in a.signal and "倒貨" not in a.signal]
        remaining_sorted = sorted(remaining, key=lambda x: (x.percent_b, -x.dip_quality_score))
        return (valid_candidates + remaining_sorted)[:limit]
    else:
        return sorted(advisories, key=lambda x: (x.percent_b, -x.dip_quality_score))[:limit]


# ───────────────────────────────────────────────────────────────
# 🔍 自由自選標的（高股息 / 權值股 / 熱門ETF）精準打擊診斷專用對照庫
# ───────────────────────────────────────────────────────────────
POPULAR_TICKERS_MAP = {
    # 💎 熱門高股息 ETF
    "00878": ("國泰永續高股息", "00878.TW", "高股息 ETF"),
    "00919": ("群益台灣精選高息", "00919.TW", "高股息 ETF"),
    "0056": ("元大高股息", "0056.TW", "高股息 ETF"),
    "00929": ("復華台灣科技優息", "00929.TW", "高股息科技 ETF"),
    "00713": ("元大台灣高息低波", "00713.TW", "高股息低波 ETF"),
    "00940": ("元大台灣價值高息", "00940.TW", "高股息價值 ETF"),
    "00939": ("統一台灣高息動能", "00939.TW", "高股息動能 ETF"),
    "00918": ("大華優利高蘋息30", "00918.TW", "高股息優利 ETF"),
    "00915": ("凱基優選高股息30", "00915.TW", "高股息優選 ETF"),
    # 🏛️ 市值與科技旗艦 ETF
    "0050": ("元大台灣50", "0050.TW", "核心市值型 ETF"),
    "006208": ("富邦台50", "006208.TW", "核心市值型 ETF"),
    "0052": ("富邦科技", "0052.TW", "科技市值型 ETF"),
    "00881": ("國泰台灣5G+", "00881.TW", "5G通訊科技 ETF"),
    "00830": ("國泰費城半導體", "00830.TW", "海外半導體 ETF"),
    # 💵 債券型 ETF
    "00679B": ("元大美債20年", "00679B.TWO", "長天期美債 ETF"),
    "00687B": ("國泰20年美債", "00687B.TWO", "長天期美債 ETF"),
    "00937B": ("群益ESG投等債20+", "00937B.TWO", "投資級公司債 ETF"),
    "00720B": ("元大投資級公司債", "00720B.TWO", "投資級公司債 ETF"),
    # 🚀 槓桿正2 ETF
    "00631L": ("元大台灣50正2", "00631L.TW", "槓桿正2 ETF"),
    "00675L": ("富邦加權正2", "00675L.TW", "槓桿正2 ETF"),
    "00685L": ("群益臺灣加權正2", "00685L.TW", "槓桿正2 ETF"),
    # 👑 台股權值股與人氣龍頭股
    "2330": ("台積電", "2330.TW", "晶圓代工龍頭"),
    "2317": ("鴻海", "2317.TW", "電子代工與AI伺服器"),
    "2454": ("聯發科", "2454.TW", "IC設計龍頭"),
    "2382": ("廣達", "2382.TW", "AI伺服器代工龍頭"),
    "2308": ("台達電", "2308.TW", "電源綠能龍頭"),
    "2603": ("長榮", "2603.TW", "貨櫃航運龍頭"),
    "3008": ("大立光", "3008.TW", "光學鏡頭龍頭"),
    "2412": ("中華電", "2412.TW", "電信防守型龍頭"),
    "2881": ("富邦金", "2881.TW", "獲利金控龍頭"),
    "2882": ("國泰金", "2882.TW", "壽險金控龍頭"),
    "2886": ("兆豐金", "2886.TW", "公股金控龍頭"),
    "2891": ("中信金", "2891.TW", "消金金控龍頭"),
    "3231": ("緯創", "3231.TW", "AI伺服器代工"),
    "2357": ("華碩", "2357.TW", "PC與AI伺服器"),
}

NAME_TO_CODE = {
    "台積電": "2330",
    "鴻海": "2317",
    "聯發科": "2454",
    "廣達": "2382",
    "台達電": "2308",
    "長榮": "2603",
    "大立光": "3008",
    "中華電": "2412",
    "富邦金": "2881",
    "國泰金": "2882",
    "兆豐金": "2886",
    "中信金": "2891",
    "緯創": "3231",
    "華碩": "2357",
    "國泰永續高股息": "00878",
    "群益台灣精選高息": "00919",
    "元大高股息": "0056",
    "元大台灣50": "0050",
    "復華台灣科技優息": "00929",
    "元大台灣高息低波": "00713",
    "元大台灣價值高息": "00940",
    "統一台灣高息動能": "00939",
    "富邦台50": "006208",
    "元大美債20年": "00679B",
    "國泰20年美債": "00687B",
    "元大台灣50正2": "00631L",
}


_CACHED_BENCH_DF = None

def get_cached_benchmark_df() -> pd.DataFrame:
    """快取加權指數對照基準，避免重複調用耗時的磁碟對齊載入"""
    global _CACHED_BENCH_DF
    if _CACHED_BENCH_DF is not None and len(_CACHED_BENCH_DF) >= 20:
        return _CACHED_BENCH_DF
    try:
        import yfinance as yf
        df = yf.download("^TWII", period="1y", interval="1d", progress=False)
        if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
            df.columns = df.columns.get_level_values(0)
        _CACHED_BENCH_DF = df
        return df
    except Exception:
        return pd.DataFrame()


def diagnose_custom_ticker(ticker_input: str) -> tuple[ETFDipAdvisory | None, pd.DataFrame | None, str]:
    """
    自選標的自由診斷核心引擎：
    支援任何台股標的代碼 (如 00878, 00919, 0056, 0050, 2330, 2317, 2454 等) 或中文名稱。
    自動串接 OHLCV 歷史行情、TWSE 籌碼與維持率、VIX、折溢價及期權共振，
    計算 9 大黃金因子檢查表與金字塔三段建倉階梯。
    """
    import yfinance as yf
    from etf_analytics import compute_etf_metrics

    raw = ticker_input.strip()
    if not raw:
        return None, None, "請輸入股票或 ETF 代碼／名稱（例如 00878 或 2330）"

    # 中文名稱映射
    clean_code = NAME_TO_CODE.get(raw, raw).upper()
    clean_code = clean_code.replace(".TW", "").replace(".TWO", "").strip()

    # 查表或推斷名稱與 Yahoo 代碼
    if clean_code in POPULAR_TICKERS_MAP:
        name, yf_symbol, category = POPULAR_TICKERS_MAP[clean_code]
    else:
        name = clean_code
        category = "台股標的"
        # 判斷是否為上櫃債券 ETF (以 B 結尾多為櫃買中心 .TWO)
        if clean_code.endswith("B"):
            yf_symbol = f"{clean_code}.TWO"
        else:
            yf_symbol = f"{clean_code}.TW"

    # 下載歷史行情
    df = yf.download(yf_symbol, period="1y", interval="1d", progress=False)
    if (df is None or len(df) < 15) and not yf_symbol.endswith(".TWO"):
        # 嘗試 .TWO (上櫃市場)
        alt_symbol = f"{clean_code}.TWO"
        alt_df = yf.download(alt_symbol, period="1y", interval="1d", progress=False)
        if alt_df is not None and len(alt_df) >= 15:
            df = alt_df
            yf_symbol = alt_symbol

    if df is None or len(df) < 15:
        return None, None, f"查無標的代碼【{clean_code}】之近期市場行情，請確認代碼是否正確。"

    # 扁平化 MultiIndex (yfinance 相容)
    if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)

    # 取得加權指數對照基準 (高效率快取)
    bench_df = get_cached_benchmark_df()


    # 抓取市場總體籌碼
    margin_data = {}
    try:
        from chip_fetcher import fetch_twse_margin_single_day, calculate_estimated_margin_maintenance_ratio
        m_info = fetch_twse_margin_single_day()
        if m_info:
            margin_data = m_info
            if bench_df is not None and "Close" in bench_df.columns:
                margin_data["est_maint_ratio"] = calculate_estimated_margin_maintenance_ratio(bench_df["Close"])
    except Exception:
        pass

    vix_data = fetch_vix_status_data()

    # 折溢價資訊 (若為個股則無折溢價)
    nav_info = None
    try:
        from chip_fetcher import fetch_twse_etf_nav_all
        nav_map = fetch_twse_etf_nav_all()
        nav_info = nav_map.get(clean_code)
    except Exception:
        pass

    # 期貨與選擇權
    deriv_data = {}
    try:
        from chip_fetcher import fetch_taifex_latest_derivatives
        deriv_data = fetch_taifex_latest_derivatives()
    except Exception:
        pass

    info_dict = {
        "ticker": yf_symbol,
        "name": name,
        "category": category,
        "type": "自選標的",
        "description": f"投資人自選診斷標的：{clean_code}"
    }

    try:
        perf = compute_etf_metrics(df, bench_df, info_dict)
        adv = evaluate_etf_dip(perf, df, bench_df, margin_data=margin_data, vix_data=vix_data, nav_info=nav_info, deriv_data=deriv_data)
        return adv, df, f"診斷成功！已完成【{clean_code} {name}】之多維共振量化分析。"
    except Exception as e:
        return None, None, f"分析計算過程中發生異常: {str(e)}"



if __name__ == "__main__":
    print("Testing Enhanced Precision Strike ETF Dip Hunter Engine...")
    dip_advs = evaluate_all_etfs_dip()
    print(f"\nEvaluated {len(dip_advs)} ETFs for Dip Opportunities:")
    top_dips = get_top_dip_picks(dip_advs)
    for idx, a in enumerate(top_dips):
        print(f"\nNo.{idx+1} [{a.perf.ticker}] {a.perf.name}: {a.star_badge} | {a.signal} (Score: {a.dip_quality_score})")
        print(f"Price: {a.perf.current_price} | Divergence: {a.divergence_type} | Pattern: {a.reversal_pattern}")
        print(f"Fib 0.618: {a.fib_0618} | Confluence: {a.is_fib_confluence} | Trend: {a.trend_alignment}")
        print(f"Scale-In: Stage 1: {a.stage1_price} | Stage 2: {a.stage2_price} | Stage 3: {a.stage3_price} | Stop: {a.stop_loss_price}")
        for r in a.reasons[:3]:
            print(f"  • {r}")
