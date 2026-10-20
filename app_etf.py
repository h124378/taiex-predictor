"""
app_etf.py - 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 每日與每月報酬率排行榜（精簡極速版）
包含：5秒高頻即時國際走勢、每日報酬排行榜、每月報酬排行榜、量化推薦前三檔
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
from datetime import datetime

from etf_analytics import calculate_all_performances, ETFPerformance
from etf_advisory import evaluate_all_etfs, ETFAdvisory, get_top_picks

# 頁面配置
st.set_page_config(
    page_title="🇹🇼 台股主動型與正2 ETF 報酬排行榜",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式（完美支援深色模式與淺色模式自適應）
st.markdown("""
<style>
    .top3-card {
        background-color: var(--secondary-background-color, #1e293b);
        color: var(--text-color, #f8fafc);
        border-radius: 12px;
        padding: 18px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.12);
        transition: transform 0.2s ease;
    }
    .top3-card:hover {
        transform: translateY(-2px);
    }
    .rank-badge {
        font-size: 1.05rem;
        font-weight: 800;
        padding: 4px 12px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 8px;
    }
    .badge-rank1 { background-color: #facc15; color: #713f12; }
    .badge-rank2 { background-color: #cbd5e1; color: #1e293b; }
    .badge-rank3 { background-color: #fdba74; color: #7c2d12; }
    
    .card-label {
        color: var(--text-color, #cbd5e1);
        opacity: 0.9;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .card-reason-box {
        background-color: rgba(148, 163, 184, 0.12);
        color: var(--text-color, #e2e8f0);
        border: 1px solid rgba(148, 163, 184, 0.18);
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.82rem;
        line-height: 1.45;
        margin-top: 6px;
    }
    .card-price-box {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 10px;
        background-color: rgba(148, 163, 184, 0.1);
        padding: 10px 14px;
        border-radius: 8px;
        border: 1px solid rgba(148, 163, 184, 0.15);
    }
    .news-pill {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 4px;
        margin-right: 6px;
    }
    .news-tag {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        font-size: 0.72rem;
        padding: 2px 6px;
        border-radius: 4px;
        margin-right: 4px;
    }
    .news-item-row {
        padding: 8px 12px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.88rem;
    }
    .news-item-row:last-child {
        border-bottom: none;
    }
    .news-item-row:hover {
        background-color: rgba(148, 163, 184, 0.08);
        border-radius: 6px;
    }
    .market-outlook-card {
        background: var(--secondary-background-color, #1e293b);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .winrate-bar-container {
        width: 100%;
        height: 16px;
        background-color: #22c55e;
        border-radius: 10px;
        overflow: hidden;
        display: flex;
        margin: 10px 0 6px 0;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.2);
    }
    .winrate-bar-up {
        background: linear-gradient(90deg, #dc2626, #ef4444);
        height: 100%;
        transition: width 0.6s ease;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=120, show_spinner=False)
def load_all_advisories(force_reload: bool = False):
    return evaluate_all_etfs(force_reload=force_reload)


@st.cache_data(ttl=120, show_spinner=False)
def load_taiex_market_outlook(force_reload: bool = False):
    """載入台股大盤加權指數多空機率與勝率預測（基於 5 年完整多空循環數據訓練之三重集成模型）"""
    try:
        from data_fetcher import build_aligned_dataset
        from predictor import TAIEXPredictor
        raw_df = build_aligned_dataset(period="5y", force_reload=force_reload)
        predictor = TAIEXPredictor()
        feats_df = predictor.build_feature_dataframe(raw_df)
        pred_res = predictor.predict_latest(feats_df)
        return pred_res
    except Exception as e:
        return None


# 側邊欄
with st.sidebar:
    st.title("🇹🇼 ETF 報酬排行榜")
    st.caption("主動式股票型 (帶A) & 槓桿正2 (帶L)")
    st.divider()

    st.subheader("⚙️ 數據操作")
    force_refresh = st.button("🔄 立即重新整理行情", use_container_width=True)

    st.divider()

    # LINE 推播設定專區
    st.subheader("📲 LINE 即時推播設定")
    from notifier_etf import (
        load_push_config, save_push_config,
        generate_line_push_message, send_line_bot_message, send_line_notify
    )
    p_cfg = load_push_config()

    push_mode = st.radio(
        "選擇 LINE 推播管道",
        ["LINE 官方帳號 (Bot)", "LINE Notify (權杖)"],
        index=0 if p_cfg.get("mode") != "notify" else 1,
        help="推薦使用 LINE 官方帳號 (Messaging API)，支援永久穩定發送至個人手機 LINE。"
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
            placeholder="例如 U4af4980629...",
            help="在 LINE Developers 專案的 Basic settings 最下方找到您的 User ID。"
        )
        
        with st.expander("📖 2 分鐘免費申請步驟說明"):
            st.markdown("""
            1. 前往 **[LINE Developers](https://developers.line.biz/console/)** 用個人 LINE 登入
            2. 建立 Provider ➜ 建立 **Messaging API Channel**
            3. 在 **Messaging API** 頁面最下方點 `Issue` 取得 **Channel Access Token**
            4. 掃描同頁面上方的 **QR Code** 加機器人為好友
            5. 在 **Basic settings** 頁面最下方複製 **Your user ID** 貼入上方
            """)

        col_save, col_test = st.columns(2)
        with col_save:
            if st.button("💾 儲存設定", use_container_width=True):
                save_push_config({
                    "mode": "bot",
                    "line_channel_token": line_token,
                    "line_user_id": line_uid
                })
                st.success("已儲存設定！")
        with col_test:
            if st.button("🚀 發送測試", use_container_width=True):
                if not line_token or not line_uid:
                    st.warning("請先填寫 Token 與 User ID！")
                else:
                    with st.spinner("發送中..."):
                        t_res = load_taiex_market_outlook()
                        msg = generate_line_push_message(load_all_advisories(), t_res)
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
        with st.expander("📖 LINE Notify 申請說明"):
            st.markdown("""
            1. 前往 **[LINE Notify 官網](https://notify-api.line.me/)** 登入
            2. 點擊右上角個人名稱 ➜ **個人頁面**
            3. 點擊 **發行權杖** ➜ 選擇「透過 1 對 1 聊天接收」➜ 複製 Token
            """)
        
        col_save2, col_test2 = st.columns(2)
        with col_save2:
            if st.button("💾 儲存設定", key="save_notify", use_container_width=True):
                save_push_config({
                    "mode": "notify",
                    "line_notify_token": notify_token
                })
                st.success("已儲存 Notify 設定！")
        with col_test2:
            if st.button("🚀 發送測試", key="test_notify", use_container_width=True):
                if not notify_token:
                    st.warning("請先填寫 Notify 權杖！")
                else:
                    with st.spinner("發送中..."):
                        t_res = load_taiex_market_outlook()
                        msg = generate_line_push_message(load_all_advisories(), t_res)
                        ok, info = send_line_notify(notify_token, msg)
                        if ok:
                            st.success(info)
                        else:
                            st.error(info)

    st.divider()
    st.caption("⚠️ **免責聲明**：本程式提供之每日/每月報酬率與推薦標的為量化統計運算，非投資建議。投資人應獨立評估自負盈虧。")


# 載入資料
with st.spinner("正在載入台股主動型與正2 ETF 最新報酬數據..."):
    try:
        advisories = load_all_advisories(force_reload=force_refresh)
    except Exception as e:
        st.error(f"載入資料失敗: {e}")
        st.stop()

if not advisories:
    st.warning("目前無有效 ETF 數據，請點擊左側重新整理。")
    st.stop()

date_str = advisories[0].perf.date

# 頁面主標題
st.markdown("""
<div style="background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%); padding: 10px 16px; border-radius: 10px; margin-bottom: 14px; border: 1px solid rgba(148, 163, 184, 0.25); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
    <div style="font-weight: 700; color: #38bdf8; font-size: 0.95rem;">
        🧭 台股量化決策導航中樞
    </div>
    <div style="display: flex; gap: 10px; font-size: 0.88rem; flex-wrap: wrap;">
        <a href="http://localhost:8500" target="_blank" style="color: #facc15; font-weight: 700; text-decoration: none; padding: 3px 10px; border-radius: 6px; background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.3);">🌐 總指揮中樞 (8500)</a>
        <a href="http://localhost:8501" target="_blank" style="color: #94a3b8; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">🏛️ 大盤多空預測 (8501)</a>
        <span style="color: #38bdf8; font-weight: 700; padding: 3px 10px; border-radius: 6px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3);">📈 ETF 動能榜 (本頁)</span>
        <a href="http://localhost:8502" target="_blank" style="color: #4ade80; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">👑 ETF 低點淘金 (8502)</a>
    </div>
</div>
""", unsafe_allow_html=True)

st.title("🇹🇼 台股主動型 (帶A) 與槓桿正2 (帶L) ETF 報酬排行榜")
st.caption(f"數據基準日：**{date_str}** ｜ 涵蓋全台灣正式掛牌主動式股票型與槓桿正2全系列標的")

# ================= 🌐 5 秒高頻即時國際市場跑馬燈 =================
@st.fragment(run_every="5s")
def render_live_global_ticker():
    from realtime_global_fetcher import fetch_realtime_global_quotes
    quotes, g_score, g_diag = fetch_realtime_global_quotes()
    now_time = datetime.now().strftime("%H:%M:%S")

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; padding: 14px 18px; color: white; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 10px; height: 10px; background-color: #ef4444; border-radius: 50%; animation: pulse 1.5s infinite;"></span>
                <b style="font-size: 1.05rem; letter-spacing: 0.5px;">🌐 國際即時走勢與台股先導風向</b>
                <span style="background: #334155; font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; color: #94a3b8;">每 5 秒自動刷新 ⚡</span>
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8;">
                最後更新: <b style="color: #38bdf8;">{now_time}</b>
            </div>
        </div>
        <div style="background: rgba(255,255,255,0.06); padding: 8px 12px; border-radius: 8px; font-size: 0.88rem; margin-bottom: 12px;">
            <b>🎯 台股先導多空評估：</b> <span style="color: {'#ef4444' if g_score >= 8 else '#22c55e' if g_score <= -8 else '#facc15'}; font-weight:bold;">{g_diag}</span>
            <span style="color:#94a3b8; font-size:0.8rem; margin-left:8px;">(多空權重分: {g_score:+.1f}/100)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if quotes:
        cols = st.columns(len(quotes))
        for idx, q in enumerate(quotes):
            with cols[idx]:
                badge_bg = "rgba(239, 68, 68, 0.15)" if q.is_up else "rgba(34, 197, 94, 0.15)"
                text_color = "#dc2626" if q.is_up else "#16a34a"
                sign = "+" if q.pct_change > 0 else ""
                st.markdown(f"""
                <div style="background: var(--secondary-background-color, rgba(255,255,255,0.06)); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <div style="font-size: 0.78rem; color: var(--text-color, #94a3b8); opacity: 0.85; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{q.name}</div>
                    <div style="font-size: 0.95rem; font-weight: bold; margin: 2px 0; color: var(--text-color, #f8fafc);">{q.price:,.2f}</div>
                    <div style="background: {badge_bg}; color: {text_color}; font-weight: bold; font-size: 0.78rem; border-radius: 4px; padding: 1px 4px; display: inline-block;">
                        {sign}{q.pct_change:.2f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)

render_live_global_ticker()

# ================= 📢 全球與台股重大財經即時新聞 =================
@st.fragment(run_every="30s")
def render_live_news_section():
    from realtime_news_fetcher import get_latest_financial_news
    news_items = get_latest_financial_news(force_refresh=False, max_count=6)

    if news_items:
        with st.expander("📢 全球與台股重大即時財經快訊（每 30 秒自動更新 ⚡）", expanded=True):
            news_html_list = []
            for n in news_items:
                sentiment_bg = "rgba(239, 68, 68, 0.18)" if n.sentiment == "利多" else "rgba(34, 197, 94, 0.18)" if n.sentiment == "利空" else "rgba(148, 163, 184, 0.15)"
                sentiment_color = "#ef4444" if n.sentiment == "利多" else "#22c55e" if n.sentiment == "利空" else "#94a3b8"
                tag_spans = "".join([f'<span class="news-tag">{t}</span>' for t in n.tags])
                
                news_html_list.append(f"""
                <div class="news-item-row">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1;">
                        <span style="color: #64748b; font-size: 0.78rem; font-family: monospace;">[{n.published_time}]</span>
                        <span class="news-pill" style="background: {sentiment_bg}; color: {sentiment_color};">{n.sentiment}</span>
                        {tag_spans}
                        <a href="{n.link}" target="_blank" style="color: var(--text-color, #f8fafc); text-decoration: none; font-weight: 500; font-size: 0.88rem;">
                            {n.title}
                        </a>
                    </div>
                    <div style="font-size: 0.75rem; color: #64748b; margin-left: 12px; white-space: nowrap;">
                        {n.source}
                    </div>
                </div>
                """)
            
            card_box = f"""
            <div style="background: var(--secondary-background-color, rgba(255,255,255,0.04)); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 4px 8px;">
                {''.join(news_html_list)}
            </div>
            """
            st.html(card_box)

render_live_news_section()

st.write("")

# ================= 🧭 整體台股多空勝率與風向預測 =================
taiex_res = load_taiex_market_outlook(force_reload=force_refresh)

if taiex_res:
    p_up = taiex_res.prob_up
    p_down = taiex_res.prob_down
    sig = taiex_res.signal
    action = taiex_res.action
    pos = taiex_res.suggested_position
    
    # 判定多空狀態與色彩 (台股紅多綠空慣例，與大盤多空診斷全面一致)
    c_score = getattr(taiex_res, "composite_score", 0.0)
    is_strong_sell = ("強力賣出" in sig) or (c_score <= -30) or ("0% ~ 10%" in pos)
    is_bearish = ("偏空" in sig) or ("賣出" in action) or (c_score <= -10)
    is_bullish = ("買進" in sig) or (c_score >= 10)

    if is_strong_sell:
        dir_badge = "❄️ 強力避險 (空頭主跌)"
        dir_color = "#22c55e"
        badge_bg = "rgba(34, 197, 94, 0.2)"
    elif is_bearish:
        dir_badge = "❄️ 偏空防禦 (弱勢震盪)"
        dir_color = "#22c55e"
        badge_bg = "rgba(34, 197, 94, 0.2)"
    elif is_bullish:
        dir_badge = "🔥 看多偏多格局"
        dir_color = "#ef4444"
        badge_bg = "rgba(239, 68, 68, 0.2)"
    else:
        dir_badge = "⚖️ 區間震盪盤整"
        dir_color = "#facc15"
        badge_bg = "rgba(250, 204, 21, 0.2)"

    outlook_html = f"""<div class="market-outlook-card">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
    <div>
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.15rem; font-weight:800; color:var(--text-color, #f8fafc);">🇹🇼 整體台股加權指數多空勝率預測</span>
            <span style="background:{badge_bg}; color:{dir_color}; font-size:0.82rem; font-weight:700; padding:2px 10px; border-radius:12px;">
                {dir_badge}
            </span>
        </div>
        <div style="font-size:0.82rem; color:#94a3b8; margin-top:3px;">
            基準日: <b>{taiex_res.date}</b> ｜ 收盤點位: <b>{taiex_res.current_close:,.2f}</b> ({'+' if taiex_res.pct_change > 0 else ''}{taiex_res.pct_change:.2f}%) ｜ 模型交叉驗證準確率: <b>{taiex_res.model_accuracy:.1f}%</b>
        </div>
    </div>
    <div style="text-align:right;">
        <span style="font-size:0.82rem; color:#94a3b8;">建議操作策略</span><br>
        <b style="font-size:1.05rem; color:{dir_color};">{action}</b>
        <span style="font-size:0.8rem; color:#cbd5e1; margin-left:6px;">(建議水位: {pos})</span>
    </div>
</div>

<div style="display:flex; justify-content:space-between; align-items:baseline; font-size:0.92rem; font-weight:700; margin-bottom:2px;">
    <span style="color:#ef4444;">🔴 看多上漲勝率: {p_up:.1f}%</span>
    <span style="color:#22c55e;">🟢 看空下跌機率: {p_down:.1f}%</span>
</div>

<div class="winrate-bar-container">
    <div class="winrate-bar-up" style="width: {p_up:.1f}%;"></div>
</div>

<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin-top:14px; padding-top:12px; border-top:1px solid rgba(148, 163, 184, 0.15); font-size:0.84rem;">
    <div><span style="color:#94a3b8;">綜合量化評分:</span> <b style="color:{'#ef4444' if taiex_res.composite_score >= 0 else '#22c55e'};">{taiex_res.composite_score:+.1f} / 100</b></div>
    <div><span style="color:#94a3b8;">技術面共識分:</span> <b style="color:{'#ef4444' if taiex_res.tech_score >= 0 else '#22c55e'};">{taiex_res.tech_score:+.0f} / 100</b></div>
    <div><span style="color:#94a3b8;">法人期現貨籌碼:</span> <b style="color:{'#ef4444' if taiex_res.chip_score >= 0 else '#22c55e'};">{taiex_res.chip_score:+.0f} / 100</b></div>
    <div><span style="color:#94a3b8;">大盤動態停損點:</span> <b style="color:#22c55e;">{taiex_res.target_stop_loss:,.1f}</b></div>
</div>
</div>"""
    st.html(outlook_html)

st.write("")

# ================= 🎯 今日量化推薦前三檔 ETF =================
st.subheader("🎯 今日量化精選推薦前三檔 ETF")
st.caption("嚴格排除高檔正乖離過大與技術面過熱追高標的，精選【多頭拉回月線守穩起漲】+【經理人長期高勝率】+【最佳盈虧比】標的")

# 使用專業防追高量化精選引擎推薦前 3 檔
top_picks = get_top_picks(advisories, limit=3)

col_r1, col_r2, col_r3 = st.columns(3)
rank_badges = [("🥇 第一名推薦", "badge-rank1", "#ffd700"), ("🥈 第二名推薦", "badge-rank2", "#94a3b8"), ("🥉 第三名推薦", "badge-rank3", "#f97316")]

for idx, (col, a) in enumerate(zip([col_r1, col_r2, col_r3], top_picks)):
    p = a.perf
    rank_title, rank_cls, border_c = rank_badges[idx]
    
    # 乖離率與安全區間色彩標註
    bias_val = getattr(p, "bias_20", 0.0)
    if bias_val > 4.0:
        bias_color = "#ef4444"
        bias_tag = "⚠️ 乖離偏高"
    elif 0.0 <= bias_val <= 2.2:
        bias_color = "#22c55e"
        bias_tag = "🎯 守穩起漲區"
    elif bias_val < 0.0:
        bias_color = "#38bdf8"
        bias_tag = "💎 負乖離整理"
    else:
        bias_color = "#facc15"
        bias_tag = "溫和"

    with col:
        card_html = f"""<div class="top3-card" style="border-top: 5px solid {border_c};">
<div style="display:flex; justify-content:space-between; align-items:center;">
    <span class="rank-badge {rank_cls}">{rank_title}</span>
    <span style="font-size:0.75rem; background:rgba(34,197,94,0.15); color:#22c55e; padding:2px 8px; border-radius:10px; font-weight:700;">{bias_tag}</span>
</div>
<h3 style="margin: 6px 0 2px 0; color: var(--text-color, #f8fafc); font-weight: 700;">{p.name} <small style="font-size:0.85rem; opacity: 0.75;">({p.ticker})</small></h3>
<div style="font-size:0.85rem; opacity: 0.85; margin-bottom:10px; color: var(--text-color, #cbd5e1);">分類: <b>{p.category}</b> ｜ 趨勢: <b>{p.ma_trend}</b></div>
<div class="card-price-box">
<div>
<span style="font-size:1.35rem; font-weight:800; color: var(--text-color, #f8fafc);">{p.current_price:.2f} 元</span>
<span style="font-size:0.92rem; font-weight:bold; color:{'#ef4444' if p.pct_change_1d >= 0 else '#22c55e'}; margin-left:6px;">
({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)
</span>
</div>
<div style="text-align:right;">
<span class="card-label">近1月累積</span><br>
<b style="font-size:1.0rem; font-weight:800; color:{'#ef4444' if p.return_1m >= 0 else '#22c55e'};">{'+' if p.return_1m > 0 else ''}{p.return_1m:.2f}%</b>
</div>
</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px;">
<div><span class="card-label">📏 月線乖離率:</span> <b style="color:{bias_color}; font-size:0.95rem;">{bias_val:+.2f}%</b></div>
<div><span class="card-label">⚡ KD / RSI:</span> <b style="color: var(--text-color, #f8fafc); font-size:0.95rem;">K:{p.k_9:.0f} / R:{p.rsi_14:.0f}</b></div>
<div><span class="card-label">🛑 建議停損:</span> <b style="color:#22c55e; font-size:0.95rem;">{a.target_stop_loss:.2f}</b></div>
<div><span class="card-label">🎯 目標停利:</span> <b style="color:#ef4444; font-size:0.95rem;">{a.target_take_profit:.2f}</b></div>
<div><span class="card-label">🏆 經理人勝率:</span> <b style="color:{'#ef4444' if p.manager_win_rate >= 50 else '#facc15'}; font-size:0.95rem;">{p.manager_win_rate:.1f}%</b></div>
<div><span class="card-label">🎖️ 經理人Alpha:</span> <b style="color: var(--text-color, #f8fafc); font-size:0.95rem;">+{p.alpha_1m:.2f}%</b></div>
<div><span class="card-label">建議操作:</span> <b style="color:#ef4444; font-size:0.95rem;">{a.signal.split(' ')[0]}</b></div>
<div><span class="card-label">近期夏普值:</span> <b style="color: var(--text-color, #f8fafc); font-size:0.95rem;">{p.sharpe_ratio:.2f}</b></div>
</div>
<div class="card-reason-box">
<b>💡 推薦理由：</b> {' ｜ '.join(a.reasons[:2])}
</div>
</div>"""
        st.html(card_html)

st.write("")
st.divider()

# ================= 🏆 每日 ＆ 🚀 每月報酬排行榜 =================
tab_daily, tab_monthly = st.tabs([
    "🏆 每日報酬率排行榜 (今日漲幅 Top)",
    "🚀 每月報酬率排行榜 (近1月累積報酬 Top)"
])

# 共用過濾選單
def build_leaderboard_table(advisories_list: list[ETFAdvisory], sort_by_col: str, ascending: bool = False):
    col_f1, col_f2 = st.columns([3, 2])
    with col_f1:
        c_filter = st.radio(
            "分類篩選",
            ["全部標的", "主動式股票型 (帶A)", "台股大盤槓桿正2 (00631L等)"],
            horizontal=True,
            key=f"cat_filter_{sort_by_col}"
        )
    with col_f2:
        search_kw = st.text_input("搜尋代號或名稱", placeholder="輸入如 00410A 或 00631L", key=f"search_{sort_by_col}")

    # 篩選
    f_advs = advisories_list
    if c_filter == "主動式股票型 (帶A)":
        f_advs = [a for a in f_advs if "A" in a.perf.ticker or "股票型" in a.perf.category]
    elif c_filter == "台股大盤槓桿正2 (00631L等)":
        f_advs = [a for a in f_advs if a.perf.category == "台股槓桿正2"]

    if search_kw:
        f_advs = [a for a in f_advs if search_kw.upper() in a.perf.ticker.upper() or search_kw in a.perf.name]

    # 轉為 DataFrame
    rows = []
    for a in f_advs:
        p = a.perf
        rows.append({
            "代號": p.ticker.replace(".TW", "").replace(".TWO", ""),
            "ETF 名稱": p.name,
            "類別": p.category,
            "收盤價": p.current_price,
            "今日漲跌": p.change,
            "今日漲幅(1D)%": p.pct_change_1d,
            "月線乖離(20MA)%": getattr(p, "bias_20", 0.0),
            "近1週%": p.return_1w,
            "近1月累積%": p.return_1m,
            "近3月%": p.return_3m,
            "年初至今%": p.return_ytd,
            "經理人勝率%": p.manager_win_rate,
            "經理人Alpha(1M)%": p.alpha_1m,
            "趨勢狀態": p.ma_trend,
            "操作建議": a.signal.split(" ")[0],
            "建議停損點": a.target_stop_loss,
            "目標停利點": a.target_take_profit
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=sort_by_col, ascending=ascending).reset_index(drop=True)
        # 加排名欄位
        df.insert(0, "排名", [f"No.{i+1}" for i in range(len(df))])

        st.dataframe(
            df,
            column_config={
                "排名": st.column_config.TextColumn(width="small"),
                "代號": st.column_config.TextColumn(width="small"),
                "ETF 名稱": st.column_config.TextColumn(width="medium"),
                "類別": st.column_config.TextColumn(width="small"),
                "收盤價": st.column_config.NumberColumn(format="%.2f"),
                "今日漲跌": st.column_config.NumberColumn(format="%+.2f"),
                "今日漲幅(1D)%": st.column_config.NumberColumn(format="%+.2f%%"),
                "月線乖離(20MA)%": st.column_config.NumberColumn(format="%+.2f%%", help="當前收盤價相對於20日均線之偏離幅度。正乖離過大(>4~5%)隨時面臨回檔修乖離，0%~2.2%且守穩為最佳低風險起漲買點。"),
                "近1週%": st.column_config.NumberColumn(format="%+.2f%%"),
                "近1月累積%": st.column_config.NumberColumn(format="%+.2f%%"),
                "近3月%": st.column_config.NumberColumn(format="%+.2f%%"),
                "年初至今%": st.column_config.NumberColumn(format="%+.2f%%"),
                "經理人勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                "經理人Alpha(1M)%": st.column_config.NumberColumn(format="%+.2f%%"),
                "建議停損點": st.column_config.NumberColumn(format="%.2f"),
                "目標停利點": st.column_config.NumberColumn(format="%.2f")
            },
            use_container_width=True,
            height=580,
            hide_index=True
        )
    else:
        st.info("查無符合篩選條件的標的。")


with tab_daily:
    st.subheader("🏆 每日報酬率排行榜（依今日漲幅由高至低）")
    build_leaderboard_table(advisories, sort_by_col="今日漲幅(1D)%", ascending=False)

with tab_monthly:
    st.subheader("🚀 每月報酬率排行榜（依近 1 個月累積報酬由高至低）")
    build_leaderboard_table(advisories, sort_by_col="近1月累積%", ascending=False)
