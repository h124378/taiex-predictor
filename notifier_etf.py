"""
notifier_etf.py - 台股主動型 (帶A) 與正2 (帶L) ETF 每日報酬與決策日報生成與推播
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from datetime import datetime
from etf_advisory import ETFAdvisory, evaluate_all_etfs, get_top_picks


def generate_etf_markdown_report(advisories: list[ETFAdvisory]) -> str:
    """產生格式優美的台股主動型與正2 ETF 每日分析日報"""
    if not advisories:
        return "# 🇹🇼 台股主動型與正2 ETF 每日分析報告 (無數據)"

    date_str = advisories[0].perf.date

    # 分類
    active_etfs = [a for a in advisories if "A.TW" in a.perf.ticker or "主動" in a.perf.category]
    leveraged_etfs = [a for a in advisories if a not in active_etfs]

    lines = [
        f"# 🇹🇼 台股主動型 (帶A) 與槓桿正2 ETF 每日報酬與買賣決策日報 ({date_str})",
        "",
        "---",
        "",
        "## 🌟 今日操作亮點總結",
    ]

    strong_buys = [a for a in advisories if "強力買進" in a.signal]
    buys = [a for a in advisories if a.signal == "偏多買進 (Buy)"]
    sells = [a for a in advisories if "賣出" in a.signal or "減碼" in a.signal]

    lines.append(f"- 🔴 **強力買進標的 ({len(strong_buys)} 檔)**： " + (", ".join([f"**{a.perf.name} ({a.perf.ticker})**" for a in strong_buys]) if strong_buys else "今日無"))
    lines.append(f"- 📈 **偏多買進標的 ({len(buys)} 檔)**： " + (", ".join([f"{a.perf.name} ({a.perf.ticker})" for a in buys]) if buys else "今日無"))
    if sells:
        lines.append(f"- ⚠️ **警戒/減碼標的 ({len(sells)} 檔)**： " + (", ".join([f"{a.perf.name} ({a.perf.ticker})" for a in sells])))

    lines.extend([
        "",
        "---",
        "",
        "## 🏆 一、台股主動式股票型 ETF (代號帶 A)",
        "| 代號 | ETF 名稱 | 最新價 | 今日漲跌 | 近1月報酬 | 經理人Alpha | 建議操作 | 建議停損價 | 目標停利價 |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])

    for a in active_etfs:
        p = a.perf
        sig_badge = "🔴 強力買進" if "強力買進" in a.signal else "📈 偏多買進" if "偏多" in a.signal else "⏸️ 觀望" if "觀望" in a.signal else "📉 減碼" if "減碼" in a.signal else "🟢 賣出"
        lines.append(f"| `{p.ticker}` | **{p.name}** | **{p.current_price}** | `{p.pct_change_1d:+.2f}%` | `{p.return_1m:+.2f}%` | `+{p.alpha_1m:+.2f}%` | {sig_badge} | `{a.target_stop_loss}` | `{a.target_take_profit}` |")

    lines.extend([
        "",
        "---",
        "",
        "## ⚡ 二、台股槓桿正2 ETF (代號帶 L)",
        "| 代號 | ETF 名稱 | 最新價 | 今日漲跌 | 近1週 | 近1月 | 近3月 | 建議操作 | 建議部位 | 停損價 |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])

    for a in leveraged_etfs:
        p = a.perf
        sig_badge = "🔴 強力買進" if "強力買進" in a.signal else "📈 偏多買進" if "偏多" in a.signal else "⏸️ 觀望" if "觀望" in a.signal else "📉 減碼" if "減碼" in a.signal else "🟢 賣出"
        lines.append(f"| `{p.ticker}` | **{p.name}** | **{p.current_price}** | `{p.pct_change_1d:+.2f}%` | `{p.return_1w:+.2f}%` | `{p.return_1m:+.2f}%` | `{p.return_3m:+.2f}%` | {sig_badge} | {a.suggested_position} | `{a.target_stop_loss}` |")

    lines.extend([
        "",
        "---",
        "",
        "## 💡 關鍵標的決策理由摘要"
    ])

    for a in (strong_buys + buys)[:6]:
        lines.append(f"### **{a.perf.name} ({a.perf.ticker}) - {a.signal}**")
        for r in a.reasons:
            lines.append(f"- {r}")
        lines.append(f"- 🎯 *進場/支撐: `{a.support_price}` | 建議停損: `{a.target_stop_loss}` | 目標停利: `{a.target_take_profit}`*")
        lines.append("")

    lines.extend([
        "---",
        "⚠️ *免責聲明：本報告由量化模型基於公開市場數據與技術指標運算生成，僅供研究參考，不構成投資保證或買賣依據。投資人應獨立判斷並自負盈虧。*"
    ])

    return "\n".join(lines)


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "push_config.json")


def load_push_config() -> dict:
    """載入推播金鑰設定"""
    if os.path.exists(CONFIG_FILE):
        try:
            import json
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_push_config(config: dict) -> bool:
    """儲存推播金鑰設定"""
    try:
        import json
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def generate_line_push_message(advisories: list[ETFAdvisory], taiex_res=None) -> str:
    """產生適合 LINE 手機螢幕閱讀的高密度精美快訊文字"""
    if not advisories:
        return "🇹🇼 台股量化決策日報：今日無有效數據。"

    date_str = advisories[0].perf.date
    lines = [
        f"🇹🇼【台股大盤勝率 & 量化 ETF 快訊】",
        f"📅 基準日：{date_str}",
        "─────────────────"
    ]

    # 1. 大盤勝率區塊
    if taiex_res:
        p_up = taiex_res.prob_up
        p_down = taiex_res.prob_down
        c_score = getattr(taiex_res, "composite_score", 0.0)

        is_strong_sell = ("強力賣出" in taiex_res.signal) or (c_score <= -30) or ("0% ~ 10%" in taiex_res.suggested_position)
        is_bearish = ("偏空" in taiex_res.signal) or ("賣出" in taiex_res.action) or (c_score <= -10)
        is_bullish = ("買進" in taiex_res.signal) or (c_score >= 10)

        if is_strong_sell:
            dir_text = "❄️ 強力避險 (空頭主跌)"
        elif is_bearish:
            dir_text = "❄️ 偏空防禦 (弱勢震盪)"
        elif is_bullish:
            dir_text = "🔥 看多偏多格局"
        else:
            dir_text = "⚖️ 區間震盪盤整"

        lines.extend([
            f"🧭【加權指數多空風向】",
            f"• 盤勢格局：{dir_text} ｜ 建議持股: {taiex_res.suggested_position}",
            f"• 多空評級：{taiex_res.signal} ({taiex_res.action})",
            f"• 模型勝率：🔴明日看多 {p_up:.1f}% vs 🟢看空 {p_down:.1f}%",
            f"• 收盤點位：{taiex_res.current_close:,.2f} ({'+' if taiex_res.pct_change > 0 else ''}{taiex_res.pct_change:.2f}%)",
            f"• 大盤動態停損：{taiex_res.target_stop_loss:,.1f} 點",
            "─────────────────"
        ])

    # 2. 量化推薦前三檔 (嚴選防追高)
    top_picks = get_top_picks(advisories, limit=3)
    rank_emojis = ["🥇 第一名推薦", "🥈 第二名推薦", "🥉 第三名推薦"]
    
    lines.append("🎯【今日量化推薦前三檔 ETF (防追高精選)】")
    for idx, a in enumerate(top_picks):
        p = a.perf
        bias_tag = "🎯守穩起漲" if 0.0 <= p.bias_20 <= 2.2 else "⚠️正乖離稍高" if p.bias_20 > 4.0 else "健全"
        lines.extend([
            f"{rank_emojis[idx]}：{p.name} ({p.ticker.split('.')[0]}) [{bias_tag}]",
            f"   • 現價：{p.current_price:.2f} 元 ({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)",
            f"   • 月線乖離：{p.bias_20:+.2f}% ｜ KD:({p.k_9:.0f},{p.d_9:.0f})",
            f"   • 經理人勝率：{p.manager_win_rate:.1f}% ｜ Alpha：+{p.alpha_1m:.2f}%",
            f"   • 建議停損：{a.target_stop_loss:.2f} ｜ 目標價：{a.target_take_profit:.2f}",
            f"   • 操作建議：{a.signal.split(' ')[0]}",
        ])
        if idx < len(top_picks) - 1:
            lines.append("")

    lines.extend([
        "─────────────────",
        "🚀【近1月累積報酬 Top 3】",
    ])
    monthly_top = sorted(advisories, key=lambda x: x.perf.return_1m, reverse=True)[:3]
    for i, m in enumerate(monthly_top):
        lines.append(f"  {i+1}. {m.perf.name} ({m.perf.ticker.split('.')[0]}): {m.perf.return_1m:+.2f}%")

    lines.extend([
        "─────────────────",
        "⚠️ 量化模型統計僅供研究參考，非投資建議。"
    ])

    return "\n".join(lines)


def generate_line_dip_push_message(dip_advisories: list, taiex_res=None) -> str:
    """產生適合 LINE 手機螢幕閱讀的【台股 ETF 相對低點淘金 & 金字塔建倉】快訊文字"""
    if not dip_advisories:
        return "🇹🇼 台股相對低點淘金日報：今日無有效數據。"

    date_str = dip_advisories[0].perf.date
    lines = [
        f"💎【台股大盤勝率 & 相對低點淘金快訊】",
        f"📅 基準日：{date_str}",
        "─────────────────"
    ]

    # 1. 大盤多空勝率風向
    if taiex_res:
        p_up = taiex_res.prob_up
        p_down = taiex_res.prob_down
        c_score = getattr(taiex_res, "composite_score", 0.0)

        is_strong_sell = ("強力賣出" in taiex_res.signal) or (c_score <= -30) or ("0% ~ 10%" in taiex_res.suggested_position)
        is_bearish = ("偏空" in taiex_res.signal) or ("賣出" in taiex_res.action) or (c_score <= -10) or (p_up < 45)

        if is_strong_sell:
            dir_text = "❄️ 強力避險 (大盤空頭主跌)"
            guard_text = "🟢 暫停盲目抄底 (全面避險防守)"
        elif is_bearish:
            dir_text = "⚠️ 偏空防禦 (弱勢震盪)"
            guard_text = "🟡 嚴格控管部位 (僅限極輕量試單)"
        else:
            dir_text = "🔥 回檔有撐 (逢低偏多)"
            guard_text = "🔴 允許低接佈局 (黃金階梯建倉)"

        defense_stop = taiex_res.target_stop_loss if taiex_res.target_stop_loss < taiex_res.current_close else round(taiex_res.current_close * 0.985, 1)

        lines.extend([
            f"🧭【加權指數多空風向】",
            f"• 盤勢格局：{dir_text} ｜ 建議持股: {taiex_res.suggested_position}",
            f"• 多空評級：{taiex_res.signal} ({taiex_res.action})",
            f"• 模型勝率：🔴明日看多 {p_up:.1f}% vs 🟢看空 {p_down:.1f}%",
            f"• 抄底防護：{guard_text}",
            f"• 收盤點位：{taiex_res.current_close:,.2f} ({'+' if taiex_res.pct_change > 0 else ''}{taiex_res.pct_change:.2f}%)",
            f"• 下檔防守：{defense_stop:,.1f} 點",
            "─────────────────"
        ])

    # 1.5 機構多空四重底氣 (融資/VIX/期貨/選擇權共振)
    if dip_advisories:
        m_ratio = dip_advisories[0].margin_maint_ratio
        m_status = dip_advisories[0].margin_status
        v_val = dip_advisories[0].vix_value
        v_status = dip_advisories[0].vix_status
        pc_r = dip_advisories[0].taifex_pc_ratio
        pc_stat = dip_advisories[0].taifex_pc_status
        tx_oi = dip_advisories[0].foreign_futures_net_oi
        tx_chg = dip_advisories[0].foreign_futures_oi_change

        tx_sqz_badge = " [🚀外資大補空單]" if tx_chg >= 3000 else " [⚠️空單壓盤]" if tx_oi <= -35000 and tx_chg < 0 else ""
        pc_badge = " [👑莊家極度超跌]" if pc_r <= 70.0 else " [⚡空方耗竭]" if pc_r <= 78.0 else ""

        lines.extend([
            f"🩸【機構多空四重底氣雷達】",
            f"• 大盤推估融資維持率：{m_ratio:.1f}% ｜ {m_status.split(' ')[0]}",
            f"• 美股 VIX 恐慌指數：{v_val:.2f} ｜ {v_status.split(' ')[0]}",
            f"• 台指選擇權 P/C Ratio：{pc_r:.1f}%{pc_badge} ｜ {pc_stat.split(' ')[0]}",
            f"• 外資大台期貨留倉：{tx_oi:+,} 口 (增減: {'+' if tx_chg>0 else ''}{tx_chg:,}口){tx_sqz_badge}",
            "─────────────────"
        ])

    # 2. 相對低點淘金前三檔 (金字塔建倉階梯)
    from etf_advisory_dip import get_top_dip_picks
    top_picks = get_top_dip_picks(dip_advisories, limit=3)
    rank_emojis = ["🥇 第一名低點精選", "🥈 第二名低點精選", "🥉 第三名低點精選"]

    lines.append("🎯【精準打擊黃金買點前三檔 (金字塔分批建倉)】")
    for idx, a in enumerate(top_picks):
        p = a.perf
        etf_m_str = f"{'+' if a.etf_margin_change > 0 else ''}{a.etf_margin_change:,} 張" if a.etf_margin_change != 0 else "0 張 (籌碼穩定)"
        wash_badge = " [🔥融資減肥]" if a.etf_margin_change < -50 else " [⚠️融資攤平]" if a.etf_margin_change > 100 else ""
        prem_badge = " [💎實質折價]" if a.premium_discount_rate < -0.10 else " [⚠️高溢價]" if a.premium_discount_rate > 0.80 else ""

        lines.extend([
            f"{rank_emojis[idx]}：{p.name} ({p.ticker.split('.')[0]})",
            f"   • 評級：{a.star_badge} (淘金分: {a.dip_quality_score:.0f})",
            f"   • 現價：{p.current_price:.2f} 元 ({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)",
            f"   • 淨值折溢：淨值 {a.etf_nav:.2f} ｜ 折溢價 {a.premium_discount_rate:+.2f}%{prem_badge}",
            f"   • 轉折型態：{a.reversal_pattern}",
            f"   • 技術背離：{a.divergence_type}",
            f"   • 籌碼動向：融資 {etf_m_str}{wash_badge} ｜ P/C: {a.taifex_pc_ratio:.1f}%",
            f"   • 位階支撐：布林%B: {a.percent_b:.2f} ｜ 量比: {a.vol_ratio_20*100:.0f}% ｜ 斐波0.618: {a.fib_0618:.2f}",
            f"   • 梯階① 試單價(30%)：{a.stage1_price:.2f} 元 (左側底倉)",
            f"   • 梯階② 加碼價(40%)：{a.stage2_price:.2f} 元 (突破加碼)",
            f"   • 梯階③ 加滿價(30%)：{a.stage3_price:.2f} 元 (順勢加滿)",
            f"   • 🛑 建議停損：{a.stop_loss_price:.2f} ｜ 🎯 目標價：{a.target_price:.2f}",
            f"   • 操作指引：{a.signal} - {a.action}",
        ])
        if idx < len(top_picks) - 1:
            lines.append("")

    lines.extend([
        "─────────────────",
        "💡【金字塔建倉紀律】",
        "• 第1批輕倉試單，確認右側突破攻擊線再加碼第2批。",
        "• 融資維持率 < 155% 或 VIX 出現避雷針見頂回落時，勝率最高！",
        "• 跌破建議停損價請嚴格執行紀律，絕不向下攤平。",
        "─────────────────",
        "⚠️ 量化模型統計僅供研究參考，非投資建議。"
    ])

    return "\n".join(lines)


def generate_line_combined_push_message(standard_advisories: list, dip_advisories: list, taiex_res=None) -> str:
    """產生包含【大盤勝率 + 相對低點淘金 + 動能強勢精選】之雙版本綜合快訊"""
    date_str = dip_advisories[0].perf.date if dip_advisories else standard_advisories[0].perf.date if standard_advisories else "今日"
    lines = [
        f"🇹🇼【台股大盤勝率 & ETF 雙策略快訊】",
        f"📅 基準日：{date_str}",
        "─────────────────"
    ]

    # 大盤風向
    if taiex_res:
        p_up = taiex_res.prob_up
        p_down = taiex_res.prob_down
        c_score = getattr(taiex_res, "composite_score", 0.0)

        is_strong_sell = ("強力賣出" in taiex_res.signal) or (c_score <= -30) or ("0% ~ 10%" in taiex_res.suggested_position)
        is_bearish = ("偏空" in taiex_res.signal) or ("賣出" in taiex_res.action) or (c_score <= -10)
        is_bullish = ("買進" in taiex_res.signal) or (c_score >= 10)

        if is_strong_sell:
            dir_text = "❄️ 強力避險 (空頭主跌)"
        elif is_bearish:
            dir_text = "❄️ 偏空防禦 (弱勢震盪)"
        elif is_bullish:
            dir_text = "🔥 看多偏多格局"
        else:
            dir_text = "⚖️ 區間震盪盤整"

        lines.extend([
            f"🧭【加權指數多空風向】",
            f"• 盤勢格局：{dir_text} ｜ {taiex_res.signal.split(' ')[0]} ({taiex_res.action})",
            f"• 多空勝率：🔴明日看多 {p_up:.1f}% vs 🟢看空 {p_down:.1f}%",
            f"• 建議持股：{taiex_res.suggested_position}",
            f"• 收盤點位：{taiex_res.current_close:,.2f} ｜ 停損：{taiex_res.target_stop_loss:,.1f} 點",
            "─────────────────"
        ])

    # 融資維持率 ＆ VIX 雙指標
    if dip_advisories:
        m_ratio = dip_advisories[0].margin_maint_ratio
        v_val = dip_advisories[0].vix_value
        lines.extend([
            f"🩸【融資維持率 ＆ 恐慌指數 VIX】",
            f"• 大盤推估融資維持率：{m_ratio:.1f}% ({dip_advisories[0].margin_status.split(' ')[0]})",
            f"• 美股 VIX 恐慌指數：{v_val:.2f} ({dip_advisories[0].vix_status.split(' ')[0]})",
            "─────────────────"
        ])

    # 相對低點淘金前二檔
    if dip_advisories:
        from etf_advisory_dip import get_top_dip_picks
        top_dips = get_top_dip_picks(dip_advisories, limit=2)
        lines.append("💎【策略一：相對低點淘金 (金字塔建倉)】")
        for idx, a in enumerate(top_dips):
            p = a.perf
            lines.extend([
                f"  No.{idx+1} {p.name} ({p.ticker.split('.')[0]}): 現價 {p.current_price:.2f} 元",
                f"     • 試單: {a.stage1_price:.2f} ｜ 加碼: {a.stage2_price:.2f} ｜ 停損: {a.stop_loss_price:.2f}",
                f"     • 目標: {a.target_price:.2f} ｜ %B: {a.percent_b:.2f} ｜ 量比: {a.vol_ratio_20*100:.0f}%"
            ])
        lines.append("─────────────────")

    # 強勢動能前二檔
    if standard_advisories:
        top_picks = get_top_picks(standard_advisories, limit=2)
        lines.append("🚀【策略二：強勢動能領導 (順勢波段)】")
        for idx, a in enumerate(top_picks):
            p = a.perf
            lines.extend([
                f"  No.{idx+1} {p.name} ({p.ticker.split('.')[0]}): 現價 {p.current_price:.2f} 元",
                f"     • 乖離: {p.bias_20:+.2f}% ｜ 經理人勝率: {p.manager_win_rate:.1f}%",
                f"     • 停損: {a.target_stop_loss:.2f} ｜ 目標: {a.target_take_profit:.2f}"
            ])
        lines.append("─────────────────")

    lines.append("⚠️ 量化模型統計僅供研究參考，非投資建議。")
    return "\n".join(lines)


def send_line_bot_message(channel_access_token: str, user_id: str, message: str) -> tuple[bool, str]:
    """
    透過 LINE 官方帳號 (Messaging API) Push Message 發送到指定個人的 LINE
    """
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token.strip()}"
    }
    payload = {
        "to": user_id.strip(),
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        if r.status_code == 200:
            return True, "發送成功！請檢查手機 LINE 訊息。"
        else:
            err_msg = r.text
            try:
                err_data = r.json()
                err_msg = err_data.get("message", err_msg)
            except Exception:
                pass
            return False, f"LINE API 回應錯誤 ({r.status_code}): {err_msg}"
    except Exception as e:
        return False, f"網路連線異常: {e}"


def send_line_notify(token: str, message: str) -> tuple[bool, str]:
    """發送 Line Notify 通知"""
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    payload = {"message": f"\n{message}"}
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=10)
        if r.status_code == 200:
            return True, "Line Notify 發送成功！"
        return False, f"Line Notify 回應錯誤碼: {r.status_code}"
    except Exception as e:
        return False, f"Line Notify 發送失敗: {e}"


def send_discord_webhook(webhook_url: str, content: str) -> bool:
    """發送 Discord Webhook 通知"""
    payload = {"content": content}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        return r.status_code in [200, 204]
    except Exception:
        return False

