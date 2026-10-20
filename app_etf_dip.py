"""
app_etf_dip.py - 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 相對低點淘金與金字塔分批建倉系統 (精準打擊皇冠版)
專門協助投資人：精準打擊、買在最黃金的買點、結合底背離、反轉K線、斐波那契黃金口袋與金字塔分批建倉
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from etf_analytics import ETFPerformance
from etf_advisory_dip import evaluate_all_etfs_dip, get_top_dip_picks, ETFDipAdvisory, diagnose_custom_ticker
from notifier_etf import load_push_config, save_push_config, send_line_bot_message, send_line_notify

# 頁面配置
st.set_page_config(
    page_title="🇹🇼 台股 ETF 精準打擊 ＆ 相對低點淘金建倉系統",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式
st.markdown("""
<style>
    .dip-card {
        background-color: var(--secondary-background-color, #1e293b);
        color: var(--text-color, #f8fafc);
        border-radius: 14px;
        padding: 18px;
        border: 1px solid rgba(56, 189, 248, 0.25);
        box-shadow: 0 4px 10px -1px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .dip-card:hover {
        transform: translateY(-3px);
        border-color: rgba(250, 204, 21, 0.7);
        box-shadow: 0 8px 16px -2px rgba(250, 204, 21, 0.15);
    }
    .ladder-box {
        background: rgba(148, 163, 184, 0.08);
        border: 1px dashed rgba(148, 163, 184, 0.3);
        border-radius: 8px;
        padding: 10px 12px;
        margin: 8px 0;
    }
    .ladder-step {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;
        font-size: 0.85rem;
    }
    .ladder-badge {
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .step-1 { background-color: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }
    .step-2 { background-color: rgba(34, 197, 94, 0.2); color: #22c55e; border: 1px solid #22c55e; }
    .step-3 { background-color: rgba(250, 204, 21, 0.2); color: #facc15; border: 1px solid #facc15; }
    
    .radar-tag {
        font-size: 0.78rem;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .crown-banner {
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.18) 0%, rgba(249, 115, 22, 0.15) 100%);
        border: 1px solid #facc15;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 18px;
    }
    .checklist-tag {
        font-size: 0.75rem;
        padding: 2px 6px;
        border-radius: 4px;
        margin-right: 4px;
        display: inline-block;
        font-weight: 600;
    }
    .tag-hit { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }
    .tag-miss { background: rgba(148, 163, 184, 0.1); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_taiex_market_outlook(force_reload: bool = False):
    try:
        from data_fetcher import build_aligned_dataset
        from predictor import TAIEXPredictor
        raw_df = build_aligned_dataset(period="5y", force_reload=force_reload)
        predictor = TAIEXPredictor()
        feats_df = predictor.build_feature_dataframe(raw_df)
        return predictor.predict_latest(feats_df)
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_all_dip_advisories(force_reload: bool = False):
    return evaluate_all_etfs_dip(force_reload=force_reload)


# 側邊欄控制
with st.sidebar:
    st.header("👑 精準打擊淘金控制台")
    st.caption("核心維度：底背離、K線吞噬/W底、斐波那契 0.618、長均線保護、金字塔建倉")

    force_refresh = st.button("🔄 重新載入最新行情數據", use_container_width=True)

    st.divider()
    st.subheader("📲 LINE 推播設定與自動排程")
    from notifier_etf import (
        load_push_config, save_push_config,
        generate_line_dip_push_message, generate_line_combined_push_message,
        send_line_bot_message, send_line_notify
    )
    p_cfg = load_push_config()

    push_mode = st.radio(
        "選擇 LINE 推播管道",
        ["LINE 官方帳號 (Bot)", "LINE Notify (權杖)"],
        index=0 if p_cfg.get("mode") != "notify" else 1,
        help="推薦使用 LINE 官方帳號 (Messaging API)，支援穩定推送至個人手機 LINE。"
    )

    strat_option = st.selectbox(
        "推播策略內容",
        ["👑 精準打擊 4~5星黃金買點 (推薦)", "🌟 雙版本合一 (大盤勝率+精準淘金+強勢動能)"],
        index=0 if p_cfg.get("strategy", "dip") == "dip" else 1
    )

    if push_mode == "LINE 官方帳號 (Bot)":
        line_token = st.text_input(
            "Channel Access Token",
            value=p_cfg.get("line_channel_token", ""),
            type="password",
            placeholder="貼上 Issue 產生的長代碼"
        )
        line_uid = st.text_input(
            "Your User ID",
            value=p_cfg.get("line_user_id", ""),
            placeholder="例如 U43b57b8abfa5e9a...",
            help="在 LINE Developers 的 Basic settings 最下方複製您的 User ID。"
        )

        col_s, col_t = st.columns(2)
        with col_s:
            if st.button("💾 儲存設定", key="save_bot_dip", use_container_width=True):
                save_push_config({
                    "mode": "bot",
                    "line_channel_token": line_token,
                    "line_user_id": line_uid,
                    "strategy": "dip" if "精準" in strat_option else "both"
                })
                st.success("已儲存設定！")
        with col_t:
            if st.button("🚀 測試發送", key="test_bot_dip", use_container_width=True):
                if not line_token or not line_uid:
                    st.warning("請先填寫 Token 與 User ID！")
                else:
                    with st.spinner("正在生成精準打擊快訊並發送至手機 LINE..."):
                        t_res = load_taiex_market_outlook()
                        dip_advs = load_all_dip_advisories()
                        if "雙版本" in strat_option:
                            from etf_advisory import evaluate_all_etfs
                            std_advs = evaluate_all_etfs()
                            msg = generate_line_combined_push_message(std_advs, dip_advs, t_res)
                        else:
                            msg = generate_line_dip_push_message(dip_advs, t_res)
                        ok, info = send_line_bot_message(line_token, line_uid, msg)
                        if ok:
                            st.success(info)
                        else:
                            st.error(info)
    else:
        notify_token = st.text_input(
            "LINE Notify 權杖 (Token)",
            value=p_cfg.get("line_notify_token", ""),
            type="password",
            placeholder="貼上 LINE Notify 產生的權杖"
        )
        col_s2, col_t2 = st.columns(2)
        with col_s2:
            if st.button("💾 儲存設定", key="save_notify_dip", use_container_width=True):
                save_push_config({
                    "mode": "notify",
                    "line_notify_token": notify_token,
                    "strategy": "dip" if "精準" in strat_option else "both"
                })
                st.success("已儲存設定！")
        with col_t2:
            if st.button("🚀 測試發送", key="test_notify_dip", use_container_width=True):
                if not notify_token:
                    st.warning("請先填寫 Notify Token！")
                else:
                    with st.spinner("正在發送至 LINE Notify..."):
                        t_res = load_taiex_market_outlook()
                        dip_advs = load_all_dip_advisories()
                        if "雙版本" in strat_option:
                            from etf_advisory import evaluate_all_etfs
                            std_advs = evaluate_all_etfs()
                            msg = generate_line_combined_push_message(std_advs, dip_advs, t_res)
                        else:
                            msg = generate_line_dip_push_message(dip_advs, t_res)
                        ok, info = send_line_notify(notify_token, msg)
                        if ok:
                            st.success(info)
                        else:
                            st.error(info)

    with st.expander("⏰ 自動每日定時推播設定指引"):
        st.markdown("""
        **本機 Windows 工作排程器 (推薦，0秒延遲)**
        - 直接雙擊執行專案目錄下的 **`setup_windows_scheduler.bat`**，即可一鍵註冊 Windows 排程（每天 08:50 準時發送，完全不受雲端塞車影響）。
        """)

    st.divider()
    st.info("💡 **精準打擊守則**：買在多重條件共振點（底背離 + 吞噬型態 + 0.618 斐波口袋 + 長均線支撐），絕不盲目抄底！")


# 載入數據
with st.spinner("正在計算 36 檔主動型與正2 ETF 之底背離、反轉型態、斐波那契 0.618 與星等評級..."):
    advisories = load_all_dip_advisories(force_reload=force_refresh)

if not advisories:
    st.warning("無法載入 ETF 數據，請點擊左側重新整理。")
    st.stop()

date_str = advisories[0].perf.date

# 主標題
st.html("""
<div style="background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%); padding: 10px 16px; border-radius: 10px; margin-bottom: 14px; border: 1px solid rgba(148, 163, 184, 0.25); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
    <div style="font-weight: 700; color: #38bdf8; font-size: 0.95rem;">
        🧭 台股量化決策導航中樞
    </div>
    <div style="display: flex; gap: 10px; font-size: 0.88rem; flex-wrap: wrap;">
        <a href="http://localhost:8500" target="_blank" style="color: #facc15; font-weight: 700; text-decoration: none; padding: 3px 10px; border-radius: 6px; background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.3);">🌐 總指揮中樞 (8500)</a>
        <a href="http://localhost:8501" target="_blank" style="color: #94a3b8; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">🏛️ 大盤多空預測 (8501)</a>
        <a href="http://localhost:8503" target="_blank" style="color: #94a3b8; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">📈 ETF 動能榜 (8503)</a>
        <span style="color: #4ade80; font-weight: 700; padding: 3px 10px; border-radius: 6px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3);">👑 ETF 低點淘金 (本頁)</span>
    </div>
</div>
""")

st.title("👑 台股 ETF 精準打擊 ＆ 相對低點淘金建倉系統")
st.caption(f"數據基準日：**{date_str}** ｜ 版本：**Precision Strike Edition (黃金買點多維共振 / 金字塔分批建倉)**")

# ================= 🌐 5 秒高頻即時國際走勢 =================
@st.fragment(run_every="5s")
def render_live_global_ticker():
    from realtime_global_fetcher import fetch_realtime_global_quotes
    quotes, g_score, g_diag = fetch_realtime_global_quotes()
    now_time = datetime.now().strftime("%H:%M:%S")

    st.html(f"""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border-radius: 12px; padding: 14px 18px; color: white; margin-bottom: 15px; border: 1px solid rgba(99, 102, 241, 0.25);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 10px; height: 10px; background-color: #38bdf8; border-radius: 50%; animation: pulse 1.5s infinite;"></span>
                <b style="font-size: 1.05rem; letter-spacing: 0.5px;">🌐 國際即時走勢與台股先導風向</b>
                <span style="background: #312e81; font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; color: #a5b4fc;">每 5 秒自動刷新 ⚡</span>
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8;">最後更新: <b style="color: #38bdf8;">{now_time}</b></div>
        </div>
        <div style="background: rgba(255,255,255,0.06); padding: 8px 12px; border-radius: 8px; font-size: 0.88rem;">
            <b>🎯 台股先導多空評估：</b> <span style="color: {'#4ade80' if g_score >= 8 else '#f87171' if g_score <= -8 else '#facc15'}; font-weight:bold;">{g_diag}</span>
            <span style="color:#94a3b8; font-size:0.8rem; margin-left:8px;">(多空權重分: {g_score:+.1f}/100)</span>
        </div>
    </div>
    """)

    if quotes:
        cols = st.columns(len(quotes))
        for idx, q in enumerate(quotes):
            with cols[idx]:
                badge_bg = "rgba(239, 68, 68, 0.15)" if q.is_up else "rgba(34, 197, 94, 0.15)"
                text_color = "#dc2626" if q.is_up else "#16a34a"
                sign = "+" if q.pct_change > 0 else ""
                st.html(f"""
                <div style="background: var(--secondary-background-color, rgba(255,255,255,0.06)); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 8px; text-align: center;">
                    <div style="font-size: 0.78rem; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{q.name}</div>
                    <div style="font-size: 0.95rem; font-weight: bold; margin: 2px 0;">{q.price:,.2f}</div>
                    <div style="background: {badge_bg}; color: {text_color}; font-weight: bold; font-size: 0.78rem; border-radius: 4px; padding: 1px 4px; display: inline-block;">
                        {sign}{q.pct_change:.2f}%
                    </div>
                </div>
                """)

render_live_global_ticker()

# ================= 🧭 大盤共振安全防護網 ＆ 🩸 四重機構底氣雷達 (融資/VIX/期貨/選擇權) =================
taiex_res = load_taiex_market_outlook(force_reload=force_refresh)

market_m_ratio = advisories[0].margin_maint_ratio if advisories else 165.0
market_m_status = advisories[0].margin_status if advisories else "常態"
vix_val = advisories[0].vix_value if advisories else 18.0
vix_stat = advisories[0].vix_status if advisories else "常態"
tx_net_oi = advisories[0].foreign_futures_net_oi if advisories else 0
tx_chg = advisories[0].foreign_futures_oi_change if advisories else 0
pc_ratio = advisories[0].taifex_pc_ratio if advisories else 95.0
pc_stat = advisories[0].taifex_pc_status if advisories else "常態"

# 狀態顏色
m_color = "#ef4444" if market_m_ratio < 145 else "#facc15" if market_m_ratio < 155 else "#38bdf8"
v_color = "#f59e0b" if "見頂" in vix_stat else "#ef4444" if vix_val >= 25 else "#38bdf8"
pc_color = "#4ade80" if pc_ratio <= 70.0 else "#facc15" if pc_ratio <= 80.0 else "#38bdf8"
tx_color = "#4ade80" if tx_chg >= 3000 else "#f87171" if tx_net_oi <= -35000 and tx_chg < 0 else "#38bdf8"

col_g1, col_g2 = st.columns([1, 1.25])

with col_g1:
    if taiex_res:
        p_up = taiex_res.prob_up
        p_down = taiex_res.prob_down
        c_score = getattr(taiex_res, "composite_score", 0.0)

        # 嚴格與大盤每日多空診斷系統全面連動
        is_strong_sell = ("強力賣出" in taiex_res.signal) or (c_score <= -30) or ("0% ~ 10%" in taiex_res.suggested_position)
        is_bearish = ("偏空" in taiex_res.signal) or ("賣出" in taiex_res.action) or (c_score <= -10) or (p_up < 45)

        if is_strong_sell:
            safe_guard_status = "🟢 大盤空頭主跌，暫停盲目抄底 (大盤全面避險)"
            guard_bg = "rgba(34, 197, 94, 0.15)"
            guard_color = "#22c55e"
        elif is_bearish:
            safe_guard_status = "🟡 大盤弱勢震盪，嚴格控管部位 (僅限極輕量試單)"
            guard_bg = "rgba(250, 204, 21, 0.15)"
            guard_color = "#facc15"
        else:
            safe_guard_status = "🔴 大盤回檔有撐，允許黃金點位分批佈局"
            guard_bg = "rgba(239, 68, 68, 0.15)"
            guard_color = "#ef4444"

        # 下檔關鍵支撐防守線 (確保防守線合理低於現價)
        defense_stop = taiex_res.target_stop_loss if taiex_res.target_stop_loss < taiex_res.current_close else round(taiex_res.current_close * 0.985, 1)

        st.html(f"""
        <div style="background: {guard_bg}; border: 1px solid {guard_color}; border-radius: 10px; padding: 12px 16px; min-height: 125px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:{guard_color}; font-size:1.0rem;">🛡️ 大盤共振安全防護網：{taiex_res.signal.split(' ')[0]}</b>
                <span style="font-size:0.8rem; background:rgba(255,255,255,0.08); padding:2px 8px; border-radius:6px; color:{guard_color}; font-weight:bold;">{taiex_res.suggested_position}</span>
            </div>
            <div style="font-size:0.95rem; font-weight:bold; margin-top:6px; color:#f8fafc;">
                {safe_guard_status}
            </div>
            <div style="font-size:0.82rem; color:#94a3b8; margin-top:6px;">
                加權收盤: <b>{taiex_res.current_close:,.2f}</b> ｜ 🔴看多機率: <b>{p_up:.1f}%</b> ｜ 下檔防守: <b>{defense_stop:,.1f}</b>
            </div>
        </div>
        """)

with col_g2:
    st.html(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 12px 16px; min-height: 125px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <b style="color:#38bdf8; font-size:1.0rem;">🩸 籌碼與衍生品四重底氣雷達</b>
            <span style="font-size:0.75rem; background:rgba(56,189,248,0.15); color:#38bdf8; padding:2px 6px; border-radius:4px;">外資/選擇權/維持率共振</span>
        </div>
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:6px;">
            <div style="background:rgba(255,255,255,0.05); padding:6px 8px; border-radius:6px; text-align:center;">
                <div style="font-size:0.72rem; color:#94a3b8;">大盤融資維持率</div>
                <div style="font-size:0.98rem; font-weight:800; color:{m_color};">{market_m_ratio:.1f}%</div>
                <div style="font-size:0.68rem; color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{market_m_status.split(' ')[0]}</div>
            </div>
            <div style="background:rgba(255,255,255,0.05); padding:6px 8px; border-radius:6px; text-align:center;">
                <div style="font-size:0.72rem; color:#94a3b8;">美股 CBOE VIX</div>
                <div style="font-size:0.98rem; font-weight:800; color:{v_color};">{vix_val:.2f}</div>
                <div style="font-size:0.68rem; color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{vix_stat.split(' ')[0]}</div>
            </div>
            <div style="background:rgba(255,255,255,0.05); padding:6px 8px; border-radius:6px; text-align:center;">
                <div style="font-size:0.72rem; color:#94a3b8;">選擇權 P/C 比率</div>
                <div style="font-size:0.98rem; font-weight:800; color:{pc_color};">{pc_ratio:.1f}%</div>
                <div style="font-size:0.68rem; color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{pc_stat.split(' ')[0]}</div>
            </div>
            <div style="background:rgba(255,255,255,0.05); padding:6px 8px; border-radius:6px; text-align:center;">
                <div style="font-size:0.72rem; color:#94a3b8;">外資大台空單回補</div>
                <div style="font-size:0.98rem; font-weight:800; color:{tx_color};">{'+' if tx_chg>0 else ''}{tx_chg:,}</div>
                <div style="font-size:0.68rem; color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">留倉{abs(tx_net_oi)//1000}k口</div>
            </div>
        </div>
    </div>
    """)

st.write("")


# ================= 👑 全市場 4~5 星極品精準打擊警示看板 =================
five_star_list = [a for a in advisories if a.golden_stars >= 4]
if five_star_list:
    st.markdown(f"""
    <div class="crown-banner">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <b style="font-size:1.15rem; color:#facc15;">👑 今日觸發【{len(five_star_list)} 檔】4 ~ 5 星頂級精準打擊黃金買點！</b>
                <div style="font-size:0.88rem; color:#e2e8f0; margin-top:4px;">
                    多維共振條件（底背離確立、K線吞噬/W底、斐波那契 0.618、季線守穩、窒息量）已強烈匯聚，為全市場勝率最高之建倉時機！
                </div>
            </div>
            <div>
                <span style="background:#854d0e; color:#fef08a; padding:4px 10px; border-radius:8px; font-weight:bold; font-size:0.85rem;">
                    強烈關注標的：{', '.join([a.perf.name for a in five_star_list[:3]])}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ================= 🎯 今日精選「精準打擊黃金買點」前三檔 =================
st.subheader("🎯 今日精選「精準打擊黃金買點」前三檔 ETF")
st.caption("透過【黃金星等 1~5星】+【底背離確認】+【反轉K線吞噬/W底】+【斐波那契 0.618】+【金字塔三段建倉】極致鎖定")

top_dips = get_top_dip_picks(advisories, limit=3)
col_d1, col_d2, col_d3 = st.columns(3)
rank_badges = [("🥇 第一名精準打擊", "#facc15"), ("🥈 第二名精準打擊", "#38bdf8"), ("🥉 第三名精準打擊", "#a855f7")]

for idx, (col, a) in enumerate(zip([col_d1, col_d2, col_d3], top_dips)):
    p = a.perf
    rank_title, border_c = rank_badges[idx]
    c_1d = "#ef4444" if p.pct_change_1d >= 0 else "#22c55e"
    
    # 九大黃金共振檢查表 (含折溢價率、外資期貨空單大回補與選擇權 P/C Ratio)
    chk_bb = "tag-hit" if a.percent_b <= 0.30 else "tag-miss"
    chk_vol = "tag-hit" if a.vol_ratio_20 <= 0.70 else "tag-miss"
    chk_div = "tag-hit" if "背離" in a.divergence_type and "無" not in a.divergence_type else "tag-miss"
    chk_pat = "tag-hit" if "吞噬" in a.reversal_pattern or "晨星" in a.reversal_pattern or "W底" in a.reversal_pattern or a.lower_shadow_ratio >= 30 else "tag-miss"
    chk_fib = "tag-hit" if a.is_fib_confluence or "守穩" in a.trend_alignment else "tag-miss"
    chk_wash = "tag-hit" if a.etf_margin_change < 0 or a.margin_maint_ratio <= 158 else "tag-miss"
    chk_vix = "tag-hit" if "見頂" in a.vix_status or "極度恐慌" in a.vix_status or a.vix_value >= 21 else "tag-miss"
    chk_prem = "tag-hit" if a.premium_discount_rate <= 0.50 else "tag-miss"
    chk_deriv = "tag-hit" if a.taifex_pc_ratio <= 75.0 or a.foreign_futures_oi_change >= 2000 else "tag-miss"

    margin_tag_text = f"{'+' if a.etf_margin_change > 0 else ''}{a.etf_margin_change}張" if a.etf_margin_change != 0 else "籌碼穩定"
    prem_color = "#4ade80" if a.premium_discount_rate < -0.10 else "#f87171" if a.premium_discount_rate > 0.80 else "#38bdf8"

    with col:
        card_html = f"""<div class="dip-card" style="border-top: 5px solid {border_c};">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <span style="font-weight:800; font-size:1.0rem; color:{border_c};">{rank_title}</span>
    <span style="background:rgba(250,204,21,0.2); color:#facc15; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:12px; border:1px solid #facc15;">
        {a.star_badge}
    </span>
</div>
<h3 style="margin:4px 0 2px 0;">{p.name} <small style="font-size:0.85rem; opacity:0.8;">({p.ticker})</small></h3>
<div style="font-size:0.85rem; opacity:0.85; margin-bottom:8px;">分類: <b>{p.category}</b> ｜ 現價: <b style="font-size:1.15rem; color:#f8fafc;">{p.current_price:.2f} 元</b> <span style="color:{c_1d}; font-weight:bold;">({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)</span></div>

<div style="margin-bottom:8px;">
    <span class="radar-tag" style="border-color:#38bdf8;">轉折型態: <b>{a.reversal_pattern.split(' ')[0]} {a.reversal_pattern.split(' ')[1] if len(a.reversal_pattern.split(' '))>1 else ''}</b></span>
    <span class="radar-tag" style="border-color:#a855f7;">底背離: <b>{a.divergence_type.split(' ')[0]} {a.divergence_type.split(' ')[1] if len(a.divergence_type.split(' '))>1 else ''}</b></span>
    <span class="radar-tag" style="border-color:{prem_color}; color:{prem_color};">折溢價: <b>{a.premium_discount_rate:+.2f}%</b></span>
    <span class="radar-tag">淨值: <b>{a.etf_nav:.2f}</b></span>
    <span class="radar-tag" style="border-color:#ec4899;">融資動向: <b>{margin_tag_text}</b></span>
    <span class="radar-tag" style="border-color:#f43f5e;">VIX: <b>{a.vix_value:.1f}</b></span>
    <span class="radar-tag" style="border-color:#38bdf8;">P/C: <b>{a.taifex_pc_ratio:.1f}%</b></span>
    <span class="radar-tag">布林%B: <b>{a.percent_b:.2f}</b></span>
    <span class="radar-tag">量比: <b>{a.vol_ratio_20*100:.0f}%</b></span>
    <span class="radar-tag">斐波0.618: <b>{a.fib_0618:.2f}</b></span>
</div>

<div style="margin: 6px 0;">
    <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:3px;">🔍 九大機構共振檢查清單：</div>
    <span class="checklist-tag {chk_bb}">{'✓' if chk_bb=='tag-hit' else '✕'} 布林超跌</span>
    <span class="checklist-tag {chk_vol}">{'✓' if chk_vol=='tag-hit' else '✕'} 窒息量</span>
    <span class="checklist-tag {chk_div}">{'✓' if chk_div=='tag-hit' else '✕'} 底背離</span>
    <span class="checklist-tag {chk_pat}">{'✓' if chk_pat=='tag-hit' else '✕'} 反轉K線</span>
    <span class="checklist-tag {chk_fib}">{'✓' if chk_fib=='tag-hit' else '✕'} 斐波支撐</span>
    <span class="checklist-tag {chk_wash}">{'✓' if chk_wash=='tag-hit' else '✕'} 融資清洗</span>
    <span class="checklist-tag {chk_vix}">{'✓' if chk_vix=='tag-hit' else '✕'} VIX反轉</span>
    <span class="checklist-tag {chk_prem}">{'✓' if chk_prem=='tag-hit' else '✕'} 折溢安全</span>
    <span class="checklist-tag {chk_deriv}">{'✓' if chk_deriv=='tag-hit' else '✕'} 期權共振</span>
</div>

<div class="ladder-box">
    <div style="font-weight:700; font-size:0.85rem; margin-bottom:6px; color:#e2e8f0;">🪜 金字塔分批建倉階梯點位：</div>
    <div class="ladder-step">
        <span class="ladder-badge step-1">第 1 批 (左側試單 30%)</span>
        <b>{a.stage1_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-2">第 2 批 (右側加碼 40%)</span>
        <b>{a.stage2_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-3">第 3 批 (順勢加滿 30%)</span>
        <b>{a.stage3_price:.2f} 元</b>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:6px; padding-top:6px; border-top:1px dashed rgba(148,163,184,0.2); font-size:0.8rem;">
        <span>🛑 嚴格停損: <b style="color:#22c55e;">{a.stop_loss_price:.2f}</b></span>
        <span>🎯 波段目標: <b style="color:#ef4444;">{a.target_price:.2f}</b></span>
    </div>
</div>

<div style="background:rgba(148,163,184,0.1); padding:8px 10px; border-radius:6px; font-size:0.8rem; line-height:1.45; margin-top:6px;">
    <b>💡 打擊依據：</b> {' ｜ '.join(a.reasons[:2])}
</div>
</div>"""
        st.html(card_html)

st.write("")
st.divider()

# ================= 🔍 任意自選標的（高股息 / 熱門個股 / 債券）精準打擊自由診斷機 =================
st.subheader("🔍 任意自選標的（高股息 / 權值龍頭 / 債券）精準打擊自由診斷機")
st.caption("支援 00878、00919、0056、0050、2330 台積電、2317 鴻海等任何台股標的，即時診斷黃金星等、9大共振檢查表與金字塔三段建倉階梯")

quick_chips = [
    ("💎 00878 國泰高股息", "00878"),
    ("🔥 00919 群益精選高息", "00919"),
    ("💰 0056 元大高股息", "0056"),
    ("🏛️ 0050 元大台灣50", "0050"),
    ("👑 2330 台積電", "2330"),
    ("⚡ 2317 鴻海", "2317"),
    ("📱 2454 聯發科", "2454"),
    ("🚢 2603 長榮", "2603"),
    ("💵 00679B 美債20年", "00679B"),
]

q_cols = st.columns(len(quick_chips))
for idx, (label, sym) in enumerate(quick_chips):
    with q_cols[idx]:
        if st.button(label, key=f"chip_{sym}", use_container_width=True):
            st.session_state["custom_ticker_query"] = sym
            st.rerun()

curr_q = st.session_state.get("custom_ticker_query", "00878")

col_input, col_btn = st.columns([4, 1])
with col_input:
    user_ticker = st.text_input("輸入股票代碼、ETF 代碼或中文名稱：", value=curr_q, key="user_ticker_input", placeholder="例如 00878, 00919, 2330, 鴻海, 0050...")
with col_btn:
    st.write("")
    run_diag = st.button("🚀 啟動精準打擊診斷", key="btn_run_diag", use_container_width=True, type="primary")

target_symbol = user_ticker.strip() if user_ticker.strip() else curr_q

if target_symbol:
    with st.spinner(f"正在全維度診斷【{target_symbol}】之底背離、K線反轉、斐波那契、融資清洗與金字塔點位..."):
        custom_adv, custom_df, custom_msg = diagnose_custom_ticker(target_symbol)

    if custom_adv and custom_df is not None:
        p = custom_adv.perf
        c_1d = "#ef4444" if p.pct_change_1d >= 0 else "#22c55e"
        
        chk_bb = "tag-hit" if custom_adv.percent_b <= 0.30 else "tag-miss"
        chk_vol = "tag-hit" if custom_adv.vol_ratio_20 <= 0.70 else "tag-miss"
        chk_div = "tag-hit" if "背離" in custom_adv.divergence_type and "無" not in custom_adv.divergence_type else "tag-miss"
        chk_pat = "tag-hit" if "吞噬" in custom_adv.reversal_pattern or "晨星" in custom_adv.reversal_pattern or "W底" in custom_adv.reversal_pattern or custom_adv.lower_shadow_ratio >= 30 else "tag-miss"
        chk_fib = "tag-hit" if custom_adv.is_fib_confluence or "守穩" in custom_adv.trend_alignment else "tag-miss"
        chk_wash = "tag-hit" if custom_adv.etf_margin_change < 0 or custom_adv.margin_maint_ratio <= 158 else "tag-miss"
        chk_vix = "tag-hit" if "見頂" in custom_adv.vix_status or "極度恐慌" in custom_adv.vix_status or custom_adv.vix_value >= 21 else "tag-miss"
        chk_prem = "tag-hit" if custom_adv.premium_discount_rate <= 0.50 else "tag-miss"
        chk_deriv = "tag-hit" if custom_adv.taifex_pc_ratio <= 75.0 or custom_adv.foreign_futures_oi_change >= 2000 else "tag-miss"

        margin_tag_text = f"{'+' if custom_adv.etf_margin_change > 0 else ''}{custom_adv.etf_margin_change}張" if custom_adv.etf_margin_change != 0 else "籌碼穩定"
        prem_color = "#4ade80" if custom_adv.premium_discount_rate < -0.10 else "#f87171" if custom_adv.premium_discount_rate > 0.80 else "#38bdf8"
        border_c = "#facc15" if custom_adv.golden_stars >= 4 else "#38bdf8" if custom_adv.golden_stars >= 3 else "#94a3b8"

        col_c1, col_c2 = st.columns([1.1, 1.3])
        with col_c1:
            custom_card_html = f"""<div class="dip-card" style="border-top: 5px solid {border_c}; background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <span style="font-weight:800; font-size:1.1rem; color:{border_c};">🎯 自選標的精準打擊診斷結果</span>
    <span style="background:rgba(250,204,21,0.2); color:#facc15; font-weight:800; font-size:0.9rem; padding:4px 12px; border-radius:12px; border:1px solid #facc15;">
        {custom_adv.star_badge}
    </span>
</div>
<h2 style="margin:6px 0 2px 0;">{p.name} <small style="font-size:0.9rem; opacity:0.8;">({p.ticker})</small></h2>
<div style="font-size:0.9rem; opacity:0.85; margin-bottom:10px;">分類: <b>{p.category}</b> ｜ 現價: <b style="font-size:1.3rem; color:#f8fafc;">{p.current_price:.2f} 元</b> <span style="color:{c_1d}; font-weight:bold;">({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)</span></div>

<div style="margin-bottom:10px;">
    <span class="radar-tag" style="border-color:#38bdf8;">轉折型態: <b>{custom_adv.reversal_pattern}</b></span>
    <span class="radar-tag" style="border-color:#a855f7;">底背離: <b>{custom_adv.divergence_type}</b></span>
    <span class="radar-tag" style="border-color:{prem_color}; color:{prem_color};">折溢價: <b>{custom_adv.premium_discount_rate:+.2f}%</b></span>
    <span class="radar-tag" style="border-color:#ec4899;">融資增減: <b>{margin_tag_text}</b></span>
    <span class="radar-tag" style="border-color:#f43f5e;">VIX: <b>{custom_adv.vix_value:.1f}</b></span>
    <span class="radar-tag" style="border-color:#38bdf8;">P/C: <b>{custom_adv.taifex_pc_ratio:.1f}%</b></span>
    <span class="radar-tag">布林%B: <b>{custom_adv.percent_b:.2f}</b></span>
    <span class="radar-tag">量比: <b>{custom_adv.vol_ratio_20*100:.0f}%</b></span>
    <span class="radar-tag">斐波0.618: <b>{custom_adv.fib_0618:.2f}</b></span>
</div>

<div style="margin: 8px 0;">
    <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:4px;">🔍 九大機構共振檢查清單：</div>
    <span class="checklist-tag {chk_bb}">{'✓' if chk_bb=='tag-hit' else '✕'} 布林超跌</span>
    <span class="checklist-tag {chk_vol}">{'✓' if chk_vol=='tag-hit' else '✕'} 窒息量</span>
    <span class="checklist-tag {chk_div}">{'✓' if chk_div=='tag-hit' else '✕'} 底背離</span>
    <span class="checklist-tag {chk_pat}">{'✓' if chk_pat=='tag-hit' else '✕'} 反轉K線</span>
    <span class="checklist-tag {chk_fib}">{'✓' if chk_fib=='tag-hit' else '✕'} 斐波支撐</span>
    <span class="checklist-tag {chk_wash}">{'✓' if chk_wash=='tag-hit' else '✕'} 融資清洗</span>
    <span class="checklist-tag {chk_vix}">{'✓' if chk_vix=='tag-hit' else '✕'} VIX反轉</span>
    <span class="checklist-tag {chk_prem}">{'✓' if chk_prem=='tag-hit' else '✕'} 折溢安全</span>
    <span class="checklist-tag {chk_deriv}">{'✓' if chk_deriv=='tag-hit' else '✕'} 期權共振</span>
</div>

<div class="ladder-box" style="margin-top:10px;">
    <div style="font-weight:700; font-size:0.92rem; margin-bottom:6px; color:#facc15;">🪜 金字塔分批建倉階梯點位：</div>
    <div class="ladder-step">
        <span class="ladder-badge step-1">第 1 批 (左側試單 30%)</span>
        <b style="font-size:1.05rem;">{custom_adv.stage1_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-2">第 2 批 (右側加碼 40%)</span>
        <b style="font-size:1.05rem;">{custom_adv.stage2_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-3">第 3 批 (順勢加滿 30%)</span>
        <b style="font-size:1.05rem;">{custom_adv.stage3_price:.2f} 元</b>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:8px; padding-top:8px; border-top:1px dashed rgba(148,163,184,0.3); font-size:0.85rem;">
        <span>🛑 嚴格停損: <b style="color:#22c55e; font-size:0.95rem;">{custom_adv.stop_loss_price:.2f} 元</b></span>
        <span>🎯 波段目標: <b style="color:#ef4444; font-size:0.95rem;">{custom_adv.target_price:.2f} 元</b></span>
    </div>
</div>

<div style="background:rgba(148,163,184,0.12); padding:10px 12px; border-radius:6px; font-size:0.83rem; line-height:1.5; margin-top:8px;">
    <b>💡 打擊研判依據：</b><br>
    {'<br>'.join(['• ' + r for r in custom_adv.reasons[:4]])}
</div>
</div>"""
            st.html(custom_card_html)

        with col_c2:
            clean_code = p.ticker.replace(".TW", "").replace(".TWO", "").strip()
            plot_df = custom_df.tail(60).copy()
            roll_m = plot_df["Close"].rolling(20).mean()
            roll_s = plot_df["Close"].rolling(20).std()
            b_up = roll_m + 2 * roll_s
            b_low = roll_m - 2 * roll_s

            fig_c = go.Figure()
            fig_c.add_trace(go.Candlestick(
                x=plot_df.index.strftime("%m-%d"),
                open=plot_df["Open"], high=plot_df["High"], low=plot_df["Low"], close=plot_df["Close"],
                name="K線",
                increasing_line_color="#ef4444", decreasing_line_color="#22c55e"
            ))
            fig_c.add_trace(go.Scatter(x=plot_df.index.strftime("%m-%d"), y=roll_m, line=dict(color="#facc15", width=1.5), name="20MA月線"))
            fig_c.add_trace(go.Scatter(x=plot_df.index.strftime("%m-%d"), y=b_up, line=dict(color="rgba(148, 163, 184, 0.4)", width=1, dash="dash"), name="布林上軌"))
            fig_c.add_trace(go.Scatter(x=plot_df.index.strftime("%m-%d"), y=b_low, line=dict(color="#38bdf8", width=1.5), name="布林下軌"))

            fig_c.add_hline(y=custom_adv.stage1_price, line_dash="dot", line_color="#38bdf8", annotation_text=f"①試單 {custom_adv.stage1_price}", annotation_position="top left")
            fig_c.add_hline(y=custom_adv.stage2_price, line_dash="dot", line_color="#22c55e", annotation_text=f"②加碼 {custom_adv.stage2_price}", annotation_position="top left")
            fig_c.add_hline(y=custom_adv.stop_loss_price, line_dash="dash", line_color="#ef4444", annotation_text=f"🛑停損 {custom_adv.stop_loss_price}", annotation_position="bottom left")

            fig_c.update_layout(
                title=f"📊 {p.name} ({clean_code}) 近期走勢與金字塔關鍵防守/建倉線",
                xaxis_rangeslider_visible=False,
                height=480,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_c, use_container_width=True)
    else:
        st.warning(custom_msg)

st.write("")
st.divider()

# ================= 📊 相對低點淘金排行榜 =================
st.subheader("📊 全市場主動型與正2 ETF 精準打擊排行榜")
st.caption("即時掃描 36 檔標的，整合「星等評級」、「指標底背離」、「反轉型態」、「折溢價率把關」、「外資期權共振」與「金字塔分批建倉點位」")

tab_stars, tab_div, tab_margin, tab_discount, tab_fib, tab_score, tab_bb, tab_dry = st.tabs([
    "👑 4~5星極品打擊榜 (精準首選)",
    "⚡ 底背離與反轉型態榜",
    "🩸 融資清洗與恐慌反轉榜",
    "💎 實質折價超值榜 (市價低於淨值)",
    "🎯 斐波那契黃金口袋榜 (0.50~0.618)",
    "💎 綜合淘金評分榜",
    "🌊 布林通道下軌極值榜",
    "🧊 極致量縮沉澱榜"
])

def render_dip_table(filtered_advisories, sort_col: str, ascending: bool = False):
    rows = []
    for a in filtered_advisories:
        p = a.perf
        rows.append({
            "代號": p.ticker.replace(".TW", "").replace(".TWO", ""),
            "ETF 名稱": p.name,
            "精準星等": a.star_badge.split(" ")[0] + " " + a.star_badge.split(" ")[1],
            "折溢價率%": a.premium_discount_rate,
            "預估淨值": a.etf_nav,
            "收盤價": p.current_price,
            "轉折型態": a.reversal_pattern.split(" ")[0] + " " + a.reversal_pattern.split(" ")[1] if len(a.reversal_pattern.split(" "))>1 else a.reversal_pattern,
            "指標底背離": a.divergence_type.split(" ")[0] + " " + a.divergence_type.split(" ")[1] if len(a.divergence_type.split(" "))>1 else a.divergence_type,
            "融資增減(張)": a.etf_margin_change,
            "VIX恐慌": a.vix_value,
            "P/C Ratio%": a.taifex_pc_ratio,
            "今日漲幅%": p.pct_change_1d,
            "淘金分": a.dip_quality_score,
            "布林%B": a.percent_b,
            "量比%": a.vol_ratio_20 * 100,
            "斐波0.618": a.fib_0618,
            "長線保護": a.trend_alignment.split(" ")[0] + " " + a.trend_alignment.split(" ")[1] if len(a.trend_alignment.split(" "))>1 else a.trend_alignment,
            "①試單價(30%)": a.stage1_price,
            "②加碼價(40%)": a.stage2_price,
            "🛑停損價": a.stop_loss_price,
            "操作建議": a.signal.split(" ")[0]
        })
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("目前無符合該篩選條件之標的。")
        return

    df = df.sort_values(by=sort_col, ascending=ascending).reset_index(drop=True)
    df.insert(0, "排名", [f"No.{i+1}" for i in range(len(df))])

    st.dataframe(
        df,
        column_config={
            "排名": st.column_config.TextColumn(width="small"),
            "代號": st.column_config.TextColumn(width="small"),
            "ETF 名稱": st.column_config.TextColumn(width="medium"),
            "精準星等": st.column_config.TextColumn(width="small", help="1~5星評級，4~5星為多維共振之極致黃金買點"),
            "折溢價率%": st.column_config.NumberColumn(format="%+.2f%%", help="負值為折價（市價低於淨值超值），高於0.8%為高溢價危險區"),
            "預估淨值": st.column_config.NumberColumn(format="%.2f", help="TWSE 官方即時預估淨值 (NAV)"),
            "收盤價": st.column_config.NumberColumn(format="%.2f"),
            "轉折型態": st.column_config.TextColumn(width="medium", help="破底翻長紅吞噬、晨星或W底探底守穩"),
            "指標底背離": st.column_config.TextColumn(width="medium", help="價格破底或平低，但 RSI 或 MACD 柱狀圖底底高"),
            "融資增減(張)": st.column_config.NumberColumn(format="%+d 張", help="負值代表融資減肥退場，籌碼乾淨"),
            "VIX恐慌": st.column_config.NumberColumn(format="%.1f", help="美股 CBOE VIX 恐慌指數，高檔回落為反轉買點"),
            "P/C Ratio%": st.column_config.NumberColumn(format="%.1f%%", help="台指選擇權 Put/Call Ratio，低於70%為極致超跌轉折點"),
            "今日漲幅%": st.column_config.NumberColumn(format="%+.2f%%"),
            "淘金分": st.column_config.NumberColumn(format="%.1f"),
            "布林%B": st.column_config.NumberColumn(format="%.2f", help="小於0.20為超跌黃金右腳"),
            "量比%": st.column_config.NumberColumn(format="%.0f%%", help="低於60%為極致量縮窒息底"),
            "斐波0.618": st.column_config.NumberColumn(format="%.2f", help="波段0.618黃金回撤支撐"),
            "長線保護": st.column_config.TextColumn(width="medium"),
            "①試單價(30%)": st.column_config.NumberColumn(format="%.2f"),
            "②加碼價(40%)": st.column_config.NumberColumn(format="%.2f"),
            "🛑停損價": st.column_config.NumberColumn(format="%.2f")
        },
        use_container_width=True,
        height=540,
        hide_index=True
    )

with tab_stars:
    star_candidates = [a for a in advisories if a.golden_stars >= 4]
    if not star_candidates:
        star_candidates = [a for a in advisories if a.golden_stars >= 3]
    render_dip_table(star_candidates, "淘金分", ascending=False)

with tab_div:
    div_candidates = [a for a in advisories if ("背離" in a.divergence_type and "無" not in a.divergence_type) or ("吞噬" in a.reversal_pattern or "晨星" in a.reversal_pattern or "W底" in a.reversal_pattern)]
    if not div_candidates:
        div_candidates = advisories
    render_dip_table(div_candidates, "淘金分", ascending=False)

with tab_margin:
    margin_candidates = [a for a in advisories if a.etf_margin_change < 0 or "見頂" in a.vix_status or "極度恐慌" in a.vix_status]
    if not margin_candidates:
        margin_candidates = advisories
    render_dip_table(margin_candidates, "淘金分", ascending=False)

with tab_discount:
    # 實質折價超值標的 (折溢價率 <= 0.05% 或 折價負數)
    disc_candidates = [a for a in advisories if a.premium_discount_rate <= 0.05]
    if not disc_candidates:
        disc_candidates = advisories
    render_dip_table(disc_candidates, "折溢價率%", ascending=True)

with tab_fib:
    fib_candidates = [a for a in advisories if a.is_fib_confluence or a.percent_b <= 0.35]
    render_dip_table(fib_candidates, "淘金分", ascending=False)

with tab_score:
    render_dip_table(advisories, "淘金分", ascending=False)

with tab_bb:
    render_dip_table(advisories, "布林%B", ascending=True)

with tab_dry:
    render_dip_table(advisories, "量比%", ascending=True)

st.caption("⚠️ **免責聲明**：本程式提供之量化指標、底背離特徵與分批進場點位為統計模型運算，非投資建議。投資人應獨立評估風險並自負盈虧。")
