"""
etf_advisory.py - 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 多因子買賣決策與風控建議引擎
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dataclasses import dataclass
from etf_analytics import ETFPerformance, calculate_all_performances


@dataclass
class ETFAdvisory:
    perf: ETFPerformance
    signal: str                # 強力買進 / 偏多買進 / 觀望續抱 / 偏空減碼 / 強力賣出
    action: str                # 積極加碼 / 分批佈局 / 續抱觀望 / 逢高減碼 / 嚴格停損
    score: float               # 多空量化評分 (-100 ~ +100)
    suggested_position: str    # 建議部位 (如: 70% ~ 100%, 0% ~ 20%)
    target_stop_loss: float    # 建議動態停損點
    target_take_profit: float  # 目標停利價
    support_price: float       # 近期關鍵支撐價
    resistance_price: float    # 近期關鍵壓力價
    reasons: list[str]         # 決策核心依據條列


def evaluate_etf_advisory(p: ETFPerformance) -> ETFAdvisory:
    """
    針對主動型與正2特性進行多因子評定：
    嚴防高檔追高，引入月線乖離率 (BIAS)、高檔過熱一票否決機制，
    並精準獎勵「多頭拉回月線守穩起漲」與「低乖離健全動能」之最佳盈虧比進場點。
    """
    score = 0
    reasons = []

    is_leveraged_2x = "正2" in p.category or p.ticker.endswith("L.TW")
    is_active_etf = "主動" in p.category or "A.TW" in p.ticker

    bias_20 = getattr(p, "bias_20", round(((p.current_price - p.sma_20) / (p.sma_20 + 1e-9)) * 100.0, 2))
    bias_5 = getattr(p, "bias_5", round(((p.current_price - p.sma_5) / (p.sma_5 + 1e-9)) * 100.0, 2))

    # ───────────────────────────────────────────────────────────
    # 0. 高檔過熱與超買檢測 (Overbought & High Bias Detection)
    # ───────────────────────────────────────────────────────────
    severe_overbought = False    # 嚴重超買 (一票否決買進)
    overbought_warning = False   # 乖離偏高預警

    if is_leveraged_2x:
        # 正2具2倍槓桿，月線正乖離 > 6.5% 即屬極度過熱，> 5.0% 屬預警
        if bias_20 >= 6.5 or (bias_20 >= 5.0 and p.rsi_14 >= 68) or (p.k_9 >= 80 and p.d_9 >= 75):
            severe_overbought = True
        elif bias_20 >= 4.5 or p.rsi_14 >= 68:
            overbought_warning = True
    else:
        # 主動式股票型 ETF，月線正乖離 > 4.0% 進入噴出高風險區，> 2.8% 屬偏高
        if bias_20 >= 4.0 or (bias_20 >= 2.8 and p.rsi_14 >= 68) or p.rsi_14 >= 72 or (p.k_9 >= 80 and p.d_9 >= 75):
            severe_overbought = True
        elif bias_20 >= 2.8 or p.rsi_14 >= 65:
            overbought_warning = True

    # ───────────────────────────────────────────────────────────
    # 1. 均線與趨勢判定 (Trend Score: -35 ~ +35)
    # ───────────────────────────────────────────────────────────
    is_bull_ma = (p.current_price > p.sma_5 > p.sma_20 > p.sma_60)
    is_bear_ma = (p.current_price < p.sma_5 < p.sma_20 < p.sma_60)

    if is_bull_ma:
        if severe_overbought:
            score += 10
            reasons.append(f"📈 均線呈多頭排列，但月線正乖離已達 {bias_20:+.2f}% 偏離過大，慎防噴出後獲利回吐。")
        elif overbought_warning:
            score += 20
            reasons.append(f"📈 均線多頭排列延續，正乖離 ({bias_20:+.2f}%) 略高，短線不宜急躁追價。")
        else:
            score += 30
            reasons.append(f"🔥 均線呈標準多頭排列 ({p.current_price} > 5MA:{p.sma_5} > 20MA:{p.sma_20})，趨勢強勁。")
    elif p.current_price > p.sma_20 and p.sma_5 > p.sma_20:
        score += 20
        reasons.append(f"📈 穩居 20MA 月線支撐之上 ({p.current_price} > {p.sma_20})，短多動能健康。")
    elif is_bear_ma:
        score -= 35
        reasons.append(f"❄️ 均線呈空頭排列 (價格失守所有均線 < 月線:{p.sma_20})，趨勢向下修正風險高。")
    elif p.current_price < p.sma_20:
        score -= 20
        reasons.append(f"📉 跌破 20MA 月線防守關卡 ({p.current_price} < {p.sma_20})，短線架構偏弱。")
    else:
        reasons.append(f"⏸️ 於月線附近震盪整理 ({p.current_price} ≈ 月線:{p.sma_20})。")

    # ───────────────────────────────────────────────────────────
    # 2. 核心精準買點：多頭拉回守穩 / 低乖離起漲 / 超跌搶反彈
    # ───────────────────────────────────────────────────────────
    if (p.current_price >= p.sma_20 * 0.99) and (0.0 <= bias_20 <= 2.2) and (p.current_price >= p.sma_60 or p.sma_20 >= p.sma_60 * 0.98):
        # 多頭拉回月線守穩：最佳盈虧比起漲買點！
        if p.k_9 > p.d_9 and p.k_9 <= 65:
            score += 35
            reasons.insert(0, f"🎯【最佳盈虧比起漲買點】多頭拉回月線支撐守穩 (正乖離僅 {bias_20:+.2f}%)，KD 黃金交叉翻揚 (K:{p.k_9:.1f} > D:{p.d_9:.1f})，風險有限、起漲勝率極高！")
        elif p.macd_osc >= -0.05 and p.rsi_14 <= 62:
            score += 25
            reasons.insert(0, f"🎯【拉回月線支撐守穩】股價緊貼月線築底獲支撐 (正乖離 {bias_20:+.2f}%)，盈虧比極佳，為健全切入點。")
    elif (0.3 <= bias_20 <= 2.5) and (p.k_9 > p.d_9) and (35 <= p.k_9 <= 65) and (45 <= p.rsi_14 <= 65):
        # 低乖離剛突破起漲
        score += 20
        reasons.append(f"🚀【低乖離動能轉強】KD 於健康區向上翻揚，月線正乖離溫和 ({bias_20:+.2f}%)，無高檔追高風險。")
    elif (bias_20 <= -4.0 and not is_leveraged_2x) or (bias_20 <= -6.5 and is_leveraged_2x) or p.rsi_14 <= 30:
        # 超跌負乖離搶反彈
        if p.k_9 > p.d_9:
            score += 20
            reasons.append(f"💎【超跌反彈契機】月線負乖離過大 ({bias_20:+.2f}%) 且 KD 低檔交叉向上，短線醞釀均值回歸報復性反彈！")
        else:
            score += 5
            reasons.append(f"💎 技術面落入超跌區 (負乖離 {bias_20:+.2f}%, RSI:{p.rsi_14:.1f})，醞釀打底。")

    # ───────────────────────────────────────────────────────────
    # 3. 乖離率過大與高檔過熱懲罰 (Anti-Chasing Penalties)
    # ───────────────────────────────────────────────────────────
    if severe_overbought:
        score -= 35
        reasons.insert(0, f"⚠️【高檔過熱警示】月線正乖離過大 ({bias_20:+.2f}%)，短線隨時面臨獲利了結回檔賣壓，嚴禁於高點追價！")
    elif overbought_warning:
        score -= 15
        reasons.append(f"⚠️【留意乖離偏高】月線正乖離達 {bias_20:+.2f}%，短線追價風險升溫，宜待拉回量縮再行切入。")

    # KD 高檔死叉
    if p.k_9 < p.d_9 and p.k_9 >= 70:
        score -= 15
        reasons.append(f"⚠️ KD 高檔死亡交叉 (K:{p.k_9:.1f} < D:{p.d_9:.1f})，短線修正修乖離機率高。")

    # RSI 超買超賣調節
    if p.rsi_14 >= 72:
        score -= 15
        reasons.append(f"⚠️ RSI(14) 達 {p.rsi_14:.1f} 進入高檔過熱區，短線多頭動能消耗過度。")
    elif p.rsi_14 <= 28:
        score += 10
        reasons.append(f"💎 RSI(14) 降至 {p.rsi_14:.1f} 進入超賣超跌區。")

    # ───────────────────────────────────────────────────────────
    # 4. MACD 動能指標 (-15 ~ +15)
    # ───────────────────────────────────────────────────────────
    if p.macd_osc > 0 and not severe_overbought:
        score += 15
        reasons.append(f"📊 MACD 處於紅柱多方攻擊區 (OSC: {p.macd_osc:+.3f})。")
    elif p.macd_osc < 0:
        score -= 15
        reasons.append(f"📊 MACD 處於綠柱空方修正區 (OSC: {p.macd_osc:+.3f})。")

    # ───────────────────────────────────────────────────────────
    # 5. 報酬、Alpha 與 經理人勝率 (-25 ~ +25)
    # ───────────────────────────────────────────────────────────
    if is_active_etf:
        if p.alpha_1m >= 2.0:
            score += 15
            reasons.append(f"🏆 主動選股 Alpha 強勁：近 1 個月大幅跑贏大盤 {p.alpha_1m:+.2f}%！")
        elif p.alpha_1m >= 0.5:
            score += 10
            reasons.append(f"✨ 主動選股展現正超額報酬 (近月領先大盤 {p.alpha_1m:+.2f}%)。")
        elif p.alpha_1m <= -2.0:
            score -= 20
            reasons.append(f"⚠️ 經理人選股遭遇逆風：近 1 個月落後大盤 {p.alpha_1m:+.2f}%。")

        # 經理人戰勝大盤勝率
        if p.manager_win_rate >= 54.0:
            score += 10
            reasons.append(f"🎖️ 經理人戰勝大盤勝率達 {p.manager_win_rate:.1f}%，選股操盤穩定性高。")
        elif p.manager_win_rate <= 44.0:
            score -= 10
            reasons.append(f"⚠️ 經理人跑贏大盤勝率偏低 ({p.manager_win_rate:.1f}%)，近期操作節奏較為被動。")

    if is_leveraged_2x:
        if p.return_1m >= 8.0 and not severe_overbought:
            score += 15
            reasons.append(f"🚀 正2槓桿複利效應啟動：近 1 個月上漲 {p.return_1m:+.2f}%。")
        elif p.return_1m <= -8.0:
            score -= 25
            reasons.append(f"🚨 正2槓桿下殺加速：近 1 個月重挫 {p.return_1m:+.2f}%，需嚴格防守！")

        if abs(p.return_1m) < 3.0 and p.volatility_ann > 25.0:
            score -= 10
            reasons.append("⚠️ 高波動無趨勢盤整：正2易受每日重設震盪耗損，建議降低部位。")

    score = float(max(min(score, 100), -100))

    # ───────────────────────────────────────────────────────────
    # 6. 訊號與操作評定 (含高檔過熱防追高一票否決)
    # ───────────────────────────────────────────────────────────
    if severe_overbought:
        # 一票否決：月線正乖離過大或指標極端過熱，嚴禁推薦強力買進！
        if score >= 10:
            signal = "高檔觀望 (Hold)"
            action = "嚴禁追高 / 續抱或部分停利"
            position = "30% ~ 50% (不追高 / 逢高收割)"
        else:
            signal = "逢高減碼 (Sell)"
            action = "逢高調節 / 分批落袋"
            position = "10% ~ 30% (防禦減碼)"
    elif overbought_warning and score > 20:
        signal = "觀望續抱 (Hold)"
        action = "耐心等待拉回 / 暫不追價"
        position = "40% ~ 55% (中性續抱)"
    else:
        if score >= 35:
            signal = "強力買進 (Strong Buy)"
            action = "拉回加碼 / 波段做多"
            position = "80% ~ 100% (重倉多頭)"
        elif score >= 12:
            signal = "偏多買進 (Buy)"
            action = "逢低佈局 / 分批買進"
            position = "50% ~ 75% (偏多持股)"
        elif score <= -35:
            signal = "強力賣出 (Strong Sell)"
            action = "嚴格停損 / 空手觀望"
            position = "0% ~ 10% (空手避險)"
        elif score <= -12:
            signal = "偏空減碼 (Sell)"
            action = "逢高減碼 / 防禦避險"
            position = "20% ~ 40% (防禦持股)"
        else:
            signal = "觀望續抱 (Hold)"
            action = "區間操作 / 暫不加碼"
            position = "40% ~ 50% (中性水位)"

    # ───────────────────────────────────────────────────────────
    # 7. 點位計算 (ATR 停損停利)
    # ───────────────────────────────────────────────────────────
    atr = p.atr_14 if p.atr_14 > 0 else p.current_price * 0.02
    support_price = round(max(p.sma_20 * 0.98, p.current_price - 1.0 * atr), 2)
    resistance_price = round(max(p.sma_5 * 1.02, p.current_price + 1.0 * atr), 2)

    if "買進" in signal:
        stop_loss = round(max(p.sma_20 * 0.985, p.current_price - 1.2 * atr), 2)
        take_profit = round(p.current_price + 1.8 * atr, 2)
    elif "賣出" in signal or "減碼" in signal:
        stop_loss = round(p.current_price + 1.0 * atr, 2)
        take_profit = round(p.current_price - 1.5 * atr, 2)
    else:
        stop_loss = round(support_price - 0.5 * atr, 2)
        take_profit = round(resistance_price + 0.5 * atr, 2)

    return ETFAdvisory(
        perf=p,
        signal=signal,
        action=action,
        score=score,
        suggested_position=position,
        target_stop_loss=stop_loss,
        target_take_profit=take_profit,
        support_price=support_price,
        resistance_price=resistance_price,
        reasons=reasons
    )


def get_top_picks(advisories: list[ETFAdvisory], limit: int = 3) -> list[ETFAdvisory]:
    """
    量化精選推薦前 N 檔：
    1. 嚴格資格篩選：必須為買進訊號 ("買進" in signal)、score >= 15、未被高檔過熱一票否決
    2. 排序依據：
       綜合得分 = score + (經理人勝率 * 0.3) + (1月Alpha * 1.5) - (max(0, 乖離率 - 2.0) * 4.0)
       徹底排除今日漲幅追高因子，優先挑選拉回月線守穩起漲與長期高勝率標的！
    """
    valid_buys = [
        a for a in advisories 
        if "買進" in a.signal and a.score >= 15
    ]

    def pick_score(a: ETFAdvisory) -> float:
        b20 = getattr(a.perf, "bias_20", 0.0)
        # 乖離率若超過 2.0%，每多 1% 扣 4 分，嚴懲高檔追高
        bias_penalty = max(0.0, b20 - 2.0) * 4.0
        return a.score + (a.perf.manager_win_rate * 0.3) + (a.perf.alpha_1m * 1.5) - bias_penalty

    if len(valid_buys) >= limit:
        return sorted(valid_buys, key=pick_score, reverse=True)[:limit]
    elif valid_buys:
        # 若合格買進標的不足，補足其餘非賣出/非減碼且乖離率溫和之標的
        remaining = [a for a in advisories if a not in valid_buys and "賣出" not in a.signal and "減碼" not in a.signal]
        remaining_sorted = sorted(remaining, key=lambda a: getattr(a.perf, "bias_20", 0.0))
        return (valid_buys + remaining_sorted)[:limit]
    else:
        # 大盤極端過熱期，挑選抗跌防守且經理人勝率最高之標的
        return sorted(advisories, key=lambda a: (a.perf.manager_win_rate, -getattr(a.perf, "bias_20", 0.0)), reverse=True)[:limit]


def evaluate_all_etfs(force_reload: bool = False) -> list[ETFAdvisory]:
    """獲取全部標的之完整績效與決策建議"""
    perfs = calculate_all_performances(force_reload=force_reload)
    advisories = [evaluate_etf_advisory(p) for p in perfs]
    
    # 依多空量化評分由高至低排序
    advisories.sort(key=lambda x: x.score, reverse=True)
    return advisories


if __name__ == "__main__":
    print("Testing ETF advisory engine...")
    advs = evaluate_all_etfs()
    print(f"\nEvaluated {len(advs)} ETFs:")
    for a in advs[:6]:
        print(f"\n[{a.perf.etf_type}] {a.perf.ticker} {a.perf.name}: {a.signal} (Score: {a.score:+.0f})")
        print(f"Price: {a.perf.current_price} | Stop-Loss: {a.target_stop_loss} | Take-Profit: {a.target_take_profit}")
        for r in a.reasons:
            print(f" - {r}")
