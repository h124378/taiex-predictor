"""
app.py - 台灣加權指數每日預測與買賣決策系統 - Streamlit 互動儀表板 (含三大法人與期貨籌碼)
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
from plotly.subplots import make_subplots
from datetime import datetime

from data_fetcher import build_aligned_dataset, get_latest_market_snapshot
from predictor import TAIEXPredictor, PredictionResult
from backtest import StrategyBacktester, BacktestMetrics
from notifier import generate_markdown_report, send_line_notify, send_discord_webhook, send_telegram_message

# 頁面配置
st.set_page_config(
    page_title="🇹🇼 台灣加權指數每日預測系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式
st.markdown("""
<style>
    .main-metric-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .badge-strong-buy {
        background-color: #dc3545;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-buy {
        background-color: #e55353;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-neutral {
        background-color: #ffc107;
        color: #212529;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-sell {
        background-color: #2eb85c;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-strong-sell {
        background-color: #198754;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    .level-card {
        border-left: 4px solid #007bff;
        background: #fdfdfd;
        padding: 10px 15px;
        margin-bottom: 8px;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .chip-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=120, show_spinner=False)
def load_data(period: str = "5y", force_reload: bool = False):
    return build_aligned_dataset(period=period, force_reload=force_reload)


@st.cache_resource(show_spinner=False)
def get_predictor_instance():
    return TAIEXPredictor()


# 側邊欄配置
with st.sidebar:
    st.title("🇹🇼 加權指數決策系統")
    st.caption("技術面 + 機器學習 + 三大法人籌碼 + 期貨OI")
    st.divider()

    st.subheader("⚙️ 系統設定")
    period_option = st.selectbox("歷史訓練資料長度", ["5y", "3y", "2y"], index=0)
    force_refresh = st.button("🔄 立即重新下載最新數據", use_container_width=True)

    st.divider()
    st.subheader("📢 盤前盤後推播設定")
    with st.expander("Line Notify / Webhook"):
        line_token = st.text_input("Line Notify Token", type="password")
        discord_url = st.text_input("Discord Webhook URL", type="password")
        tg_token = st.text_input("Telegram Bot Token", type="password")
        tg_chat_id = st.text_input("Telegram Chat ID")

    st.divider()
    st.caption("⚠️ **免責聲明**：本程式提供之預測與訊號僅供量化研究與學術探討，非任何形式之投資建議。投資人應獨立評估自負盈虧。")


# 載入數據
with st.spinner("正在載入跨市場行情、三大法人現貨與期貨未平倉數據..."):
    try:
        raw_df = load_data(period=period_option, force_reload=force_refresh)
        predictor = get_predictor_instance()
        feats_df = predictor.build_feature_dataframe(raw_df)
        pred_res = predictor.predict_latest(feats_df)
        snap = get_latest_market_snapshot()
    except Exception as e:
        st.error(f"資料載入或預測過程發生錯誤: {e}")
        st.stop()


# 頁面標題
st.markdown("""
<div style="background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%); padding: 10px 16px; border-radius: 10px; margin-bottom: 14px; border: 1px solid rgba(148, 163, 184, 0.25); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
    <div style="font-weight: 700; color: #38bdf8; font-size: 0.95rem;">
        🧭 台股量化決策導航中樞
    </div>
    <div style="display: flex; gap: 10px; font-size: 0.88rem; flex-wrap: wrap;">
        <a href="http://localhost:8500" target="_blank" style="color: #facc15; font-weight: 700; text-decoration: none; padding: 3px 10px; border-radius: 6px; background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.3);">🌐 總指揮中樞 (8500)</a>
        <span style="color: #38bdf8; font-weight: 700; padding: 3px 10px; border-radius: 6px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3);">🏛️ 大盤多空預測 (本頁)</span>
        <a href="http://localhost:8503" target="_blank" style="color: #94a3b8; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">📈 ETF 動能榜 (8503)</a>
        <a href="http://localhost:8502" target="_blank" style="color: #4ade80; text-decoration: none; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05);">👑 ETF 低點淘金 (8502)</a>
    </div>
</div>
""", unsafe_allow_html=True)

st.title("🇹🇼 台灣加權指數（台股大盤）每日多空預測與籌碼診斷系統")
st.caption(f"觀測基準日：**{pred_res.date}** ｜ 整合美股前夜先導、台股技術指標、三大法人現貨買賣超與台指期 OI")

# 🌐 即時國際市場 5 秒自動高頻刷新片段
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
            <b>🎯 即時多空先導評估：</b> <span style="color: {'#4ade80' if g_score >= 10 else '#f87171' if g_score <= -10 else '#facc15'}; font-weight:bold;">{g_diag}</span>
            <span style="color:#94a3b8; font-size:0.8rem; margin-left:8px;">(多空權重分: {g_score:+.1f}/100)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if quotes:
        cols = st.columns(len(quotes))
        for idx, q in enumerate(quotes):
            with cols[idx]:
                badge_bg = "rgba(34, 197, 94, 0.15)" if q.is_up else "rgba(239, 68, 68, 0.15)"
                text_color = "#16a34a" if q.is_up else "#dc2626"
                sign = "+" if q.pct_change > 0 else ""
                st.markdown(f"""
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                    <div style="font-size: 0.78rem; color: #64748b; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{q.name}</div>
                    <div style="font-size: 0.95rem; font-weight: bold; margin: 2px 0; color: #0f172a;">{q.price:,.2f}</div>
                    <div style="background: {badge_bg}; color: {text_color}; font-weight: bold; font-size: 0.78rem; border-radius: 4px; padding: 1px 4px; display: inline-block;">
                        {sign}{q.pct_change:.2f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)

render_live_global_ticker()

st.write("")

# 頂部快照指標列 (Market & Chip Snapshot Bar)
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric(
        label="🇹🇼 加權指數",
        value=f"{pred_res.current_close:,.2f}",
        delta=f"{pred_res.change:+,.2f} ({pred_res.pct_change:+.2f}%)",
        delta_color="normal"
    )
with col2:
    f_str = f"連買{abs(pred_res.foreign_consec_days)}天" if pred_res.foreign_consec_days > 0 else f"連賣{abs(pred_res.foreign_consec_days)}天" if pred_res.foreign_consec_days < 0 else "持平"
    st.metric(
        label="🏦 外資現貨買賣超",
        value=f"{pred_res.foreign_net_buy:+.2f} 億",
        delta=f_str,
        delta_color="normal"
    )
with col3:
    oi_color = "normal" if pred_res.tx_foreign_net_oi > 0 else "inverse" if pred_res.tx_foreign_net_oi < -35000 else "off"
    st.metric(
        label="⚔️ 外資大台期貨淨OI",
        value=f"{pred_res.tx_foreign_net_oi:+,d} 口",
        delta=f"多空比 {pred_res.tx_foreign_ls_ratio:.2f}",
        delta_color=oi_color
    )
with col4:
    tsm = snap.get("TSMC_ADR")
    if tsm:
        st.metric(
            label="🇺🇸 台積電 ADR (TSM)",
            value=f"${tsm['close']:.2f}",
            delta=f"{tsm['pct_change']:+.2f}%",
            delta_color="normal"
        )
with col5:
    sox = snap.get("SOX")
    if sox:
        st.metric(
            label="🇺🇸 費城半導體 (^SOX)",
            value=f"{sox['close']:,.2f}",
            delta=f"{sox['pct_change']:+.2f}%",
            delta_color="normal"
        )
with col6:
    twd = snap.get("USDTWD")
    if twd:
        st.metric(
            label="💱 美元兌新台幣",
            value=f"{twd['close']:.2f}",
            delta=f"{twd['pct_change']:+.2f}%",
            delta_color="inverse"
        )

st.divider()

# 分頁籤導航
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 今日預測與決策",
    "🏦 三大法人與期貨籌碼",
    "📊 K線與指標全圖",
    "💡 多因子診斷細項",
    "📈 策略歷史回測",
    "📋 每日報告與推播"
])

# ================= TAB 1: 今日預測與決策 =================
with tab1:
    left_col, right_col = st.columns([5, 4])

    with left_col:
        st.subheader("🎯 核心決策與多空評級")

        badge_class = "badge-neutral"
        badge_icon = "⏸️"
        if "強力買進" in pred_res.signal:
            badge_class = "badge-strong-buy"
            badge_icon = "🔴🚀"
        elif "偏多" in pred_res.signal:
            badge_class = "badge-buy"
            badge_icon = "📈"
        elif "強力賣出" in pred_res.signal:
            badge_class = "badge-strong-sell"
            badge_icon = "🟢🚨"
        elif "偏空" in pred_res.signal:
            badge_class = "badge-sell"
            badge_icon = "📉"

        st.markdown(f"""
        <div style="background: #ffffff; border: 2px solid #e0e0e0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 0.9rem; color: #6c757d; font-weight: bold;">【{pred_res.date} 預測】</span>
                    <h2 style="margin: 5px 0 0 0; color: #212529;">{badge_icon} {pred_res.signal}</h2>
                </div>
                <div>
                    <span class="{badge_class}">{pred_res.action}</span>
                </div>
            </div>
            <hr style="margin: 15px 0;">
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div>
                    <p style="margin:0; color:#6c757d; font-size:0.85rem;">建議持股水位</p>
                    <h4 style="margin:0; color:#0d6efd;">{pred_res.suggested_position}</h4>
                </div>
                <div>
                    <p style="margin:0; color:#6c757d; font-size:0.85rem;">技術面共識分</p>
                    <h4 style="margin:0; color:{'#dc3545' if pred_res.tech_score >= 0 else '#198754'};">{pred_res.tech_score:+.0f} / 100</h4>
                </div>
                <div>
                    <p style="margin:0; color:#6c757d; font-size:0.85rem;">籌碼面評分</p>
                    <h4 style="margin:0; color:{'#dc3545' if pred_res.chip_score >= 0 else '#198754'};">{pred_res.chip_score:+.0f} / 100</h4>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=pred_res.prob_up,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "<b>🤖 AI 預測明日上漲機率</b>", 'font': {'size': 18}},
            number={'suffix': "%", 'font': {'size': 32}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "#d62728" if pred_res.prob_up >= 50 else "#2ca02c"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 40], 'color': '#d4edda'},
                    {'range': [40, 60], 'color': '#fff3cd'},
                    {'range': [60, 100], 'color': '#ffcccc'}
                ],
                'threshold': {
                    'line': {'color': "#d62728", 'width': 4},
                    'thickness': 0.75,
                    'value': 50
                }
            }
        ))
        fig_gauge.update_layout(height=240, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with right_col:
        st.subheader("🛡️ 關鍵點位與風控指引")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #198754;">
                <span style="font-size:0.8rem; color:#6c757d;">建議動態停損點</span>
                <h3 style="color:#198754; margin:2px 0;">{pred_res.target_stop_loss:,.1f}</h3>
                <small style="color:#6c757d;">跌破請嚴格執行紀律</small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #0dcaf0;">
                <span style="font-size:0.8rem; color:#6c757d;">第一支撐關卡 (S1)</span>
                <h4 style="margin:2px 0;">{pred_res.support_1:,.1f}</h4>
                <small style="color:#6c757d;">回檔關鍵防守點</small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #6c757d;">
                <span style="font-size:0.8rem; color:#6c757d;">預期今日低點</span>
                <h4 style="margin:2px 0;">{pred_res.expected_low:,.1f}</h4>
                <small style="color:#6c757d;">波動區間下緣</small>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #dc3545;">
                <span style="font-size:0.8rem; color:#6c757d;">目標停利點位</span>
                <h3 style="color:#dc3545; margin:2px 0;">{pred_res.target_take_profit:,.1f}</h3>
                <small style="color:#6c757d;">達標可分批獲利</small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #ffc107;">
                <span style="font-size:0.8rem; color:#6c757d;">第一壓力關卡 (R1)</span>
                <h4 style="margin:2px 0;">{pred_res.resistance_1:,.1f}</h4>
                <small style="color:#6c757d;">短線反彈遇壓點</small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="level-card" style="border-left-color: #6c757d;">
                <span style="font-size:0.8rem; color:#6c757d;">預期今日高點</span>
                <h4 style="margin:2px 0;">{pred_res.expected_high:,.1f}</h4>
                <small style="color:#6c757d;">波動區間上緣</small>
            </div>
            """, unsafe_allow_html=True)

    st.subheader("💡 決策核心依據條列")
    for r in pred_res.reasons:
        st.info(r)


# ================= TAB 2: 三大法人與期貨籌碼 =================
with tab2:
    st.subheader("🏦 三大法人現貨買賣超與台指期貨未平倉（OI）分析")
    st.caption("即時追蹤外資主力現貨進出金額、連買連賣天數與期貨避險/多空淨部位")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        f_val = pred_res.foreign_net_buy
        f_color = "#dc3545" if f_val >= 0 else "#198754"
        st.markdown(f"""
        <div class="chip-card">
            <span style="color:#6c757d; font-size:0.85rem;">外資現貨買賣超</span>
            <h3 style="color:{f_color}; margin:3px 0;">{f_val:+.2f} 億</h3>
            <small>{'連買 ' + str(pred_res.foreign_consec_days) + ' 天' if pred_res.foreign_consec_days > 0 else '連賣 ' + str(abs(pred_res.foreign_consec_days)) + ' 天' if pred_res.foreign_consec_days < 0 else '買賣平衡'}</small>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        t_val = pred_res.trust_net_buy
        t_color = "#dc3545" if t_val >= 0 else "#198754"
        st.markdown(f"""
        <div class="chip-card">
            <span style="color:#6c757d; font-size:0.85rem;">投信現貨買賣超</span>
            <h3 style="color:{t_color}; margin:3px 0;">{t_val:+.2f} 億</h3>
            <small>內資與 ETF 被動基金</small>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        d_val = pred_res.dealer_net_buy
        d_color = "#dc3545" if d_val >= 0 else "#198754"
        st.markdown(f"""
        <div class="chip-card">
            <span style="color:#6c757d; font-size:0.85rem;">自營商買賣超</span>
            <h3 style="color:{d_color}; margin:3px 0;">{d_val:+.2f} 億</h3>
            <small>自營買賣與權證避險</small>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        tot_val = pred_res.total_inst_net_buy
        tot_color = "#dc3545" if tot_val >= 0 else "#198754"
        st.markdown(f"""
        <div class="chip-card">
            <span style="color:#6c757d; font-size:0.85rem;">三大法人合計</span>
            <h3 style="color:{tot_color}; margin:3px 0;">{tot_val:+.2f} 億</h3>
            <small>現貨主力合計資金</small>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 圖表區間切換
    chip_range = st.radio("籌碼圖表顯示長度", ["1 個月", "3 個月", "6 個月", "1 年"], horizontal=True, index=1)
    chip_days_map = {"1 個月": 22, "3 個月": 65, "6 個月": 130, "1 年": 250}
    c_df = feats_df.iloc[-chip_days_map[chip_range]:].copy()

    # 圖表 1: 三大法人現貨買賣超柱狀圖
    fig_chips = go.Figure()
    fig_chips.add_trace(go.Bar(
        x=c_df.index,
        y=c_df['Foreign_Net_Buy'],
        name='外資買賣超 (億)',
        marker_color=['#ef5350' if v >= 0 else '#26a69a' for v in c_df['Foreign_Net_Buy']]
    ))
    fig_chips.add_trace(go.Bar(
        x=c_df.index,
        y=c_df['Trust_Net_Buy'],
        name='投信買賣超 (億)',
        marker_color='#ff9800',
        opacity=0.7
    ))
    fig_chips.add_trace(go.Scatter(
        x=c_df.index,
        y=c_df['Foreign_Net_Buy_5d'],
        name='外資5日累計買賣超',
        line=dict(color='#2196f3', width=2)
    ))
    fig_chips.update_layout(
        title="三大法人每日現貨買賣超金額 (億元)",
        yaxis_title="金額 (億 NTD)",
        barmode='group',
        height=380,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_chips, use_container_width=True)

    # 圖表 2: 台指期貨外資未平倉淨口數 (OI) 走勢
    fig_oi = go.Figure()
    fig_oi.add_trace(go.Scatter(
        x=c_df.index,
        y=c_df['TX_Foreign_Net_OI'],
        name='外資大台期貨淨OI (口)',
        fill='tozeroy',
        line=dict(color='#9c27b0', width=2.2)
    ))
    # 警戒參考線
    fig_oi.add_hline(y=0, line_dash="solid", line_color="black", annotation_text="0 (多空分水嶺)")
    fig_oi.add_hline(y=-35000, line_dash="dash", line_color="green", annotation_text="-35,000 口 (重度避險警戒)")
    fig_oi.add_hline(y=+5000, line_dash="dash", line_color="red", annotation_text="+5,000 口 (偏多攻擊)")

    fig_oi.update_layout(
        title="外資台指期貨大台未平倉淨口數 (TX Foreign Net OI)",
        yaxis_title="淨未平倉口數 (Contracts)",
        height=340,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_oi, use_container_width=True)


# ================= TAB 3: K線與技術指標全圖 =================
with tab3:
    st.subheader("📊 台灣加權指數技術線圖與指標分析")

    time_range = st.radio("顯示區間", ["3 個月", "6 個月", "1 年", "2 年", "全部"], horizontal=True, index=2)
    days_map = {"3 個月": 65, "6 個月": 130, "1 年": 250, "2 年": 500, "全部": len(feats_df)}
    display_df = feats_df.iloc[-days_map[time_range]:].copy()

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.50, 0.15, 0.18, 0.17],
        subplot_titles=("加權指數 K 線與布林通道 / 均線", "成交量 (Volume)", "MACD 動能指標", "RSI / KD 震盪指標")
    )

    fig.add_trace(go.Candlestick(
        x=display_df.index,
        open=display_df['Open'],
        high=display_df['High'],
        low=display_df['Low'],
        close=display_df['Close'],
        name='加權指數',
        increasing_line_color='#ef5350',
        decreasing_line_color='#26a69a'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['SMA_5'], name='5MA (週線)', line=dict(color='#ff9800', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['SMA_20'], name='20MA (月線)', line=dict(color='#2196f3', width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['SMA_60'], name='60MA (季線)', line=dict(color='#9c27b0', width=1.8)), row=1, col=1)

    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['BB_Upper'], name='布林上軌', line=dict(color='rgba(100,100,100,0.3)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['BB_Lower'], name='布林下軌', line=dict(color='rgba(100,100,100,0.3)', dash='dot'), fill='tonexty', fillcolor='rgba(200,200,200,0.1)'), row=1, col=1)

    vol_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(display_df['Close'], display_df['Open'])]
    fig.add_trace(go.Bar(x=display_df.index, y=display_df['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['VMA_5'], name='5日均量', line=dict(color='orange', width=1)), row=2, col=1)

    osc_colors = ['#ef5350' if v >= 0 else '#26a69a' for v in display_df['MACD_OSC']]
    fig.add_trace(go.Bar(x=display_df.index, y=display_df['MACD_OSC'], name='MACD 柱狀圖', marker_color=osc_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['MACD_DIF'], name='DIF', line=dict(color='red', width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['MACD_DEA'], name='DEA (MACD)', line=dict(color='blue', width=1.2)), row=3, col=1)

    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['RSI_14'], name='RSI(14)', line=dict(color='#8e44ad', width=1.5)), row=4, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['K_9'], name='K(9)', line=dict(color='#e67e22', width=1.2)), row=4, col=1)
    fig.add_trace(go.Scatter(x=display_df.index, y=display_df['D_9'], name='D(9)', line=dict(color='#2980b9', width=1.2)), row=4, col=1)

    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

    fig.update_layout(
        height=850,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)


# ================= TAB 4: 多因子診斷細項 =================
with tab4:
    st.subheader("💡 多因子技術診斷與籌碼量化評定")

    diag_data = []
    for d in pred_res.diagnostics:
        diag_data.append({
            "指標類別": d["category"],
            "狀態判定": d["status"],
            "評分權重": f"{d['score']:+d}",
            "詳細診斷依據": d["desc"]
        })
    st.dataframe(pd.DataFrame(diag_data), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🤖 AI 模型 Top 8 關鍵影響因子 (Feature Importance)")

    if not predictor.feature_importance_df.empty:
        top_df = predictor.feature_importance_df.head(8).sort_values(by="importance", ascending=True)
        fig_imp = go.Figure(go.Bar(
            x=top_df["importance"],
            y=top_df["feature"],
            orientation='h',
            marker_color='#0d6efd'
        ))
        fig_imp.update_layout(
            title="機器學習隨機森林特徵重要度權重",
            xaxis_title="相對重要度 (Importance)",
            yaxis_title="特徵變數",
            height=340,
            margin=dict(l=10, r=10, t=40, b=20)
        )
        st.plotly_chart(fig_imp, use_container_width=True)


# ================= TAB 5: 策略歷史回測 =================
with tab5:
    st.subheader("📈 策略歷史步進式回測 (Walk-Forward Backtesting)")
    st.caption("模擬過去每日依據 AI、技術與籌碼訊號自動調整持股部位的實際成效")

    c1, c2, c3 = st.columns(3)
    with c1:
        test_days_input = st.slider("回測交易日數 (約 250 日為 1 年)", min_value=60, max_value=500, value=200, step=10)
    with c2:
        capital_input = st.number_input("初始資金 (NTD)", value=1_000_000, step=100_000)
    with c3:
        run_bt_btn = st.button("🚀 執行策略回測", use_container_width=True)

    if run_bt_btn or "backtest_result" not in st.session_state:
        with st.spinner("正在進行步進式歷史回測模擬..."):
            tester = StrategyBacktester(initial_capital=capital_input)
            bt_metrics, bt_df = tester.run_backtest(raw_df, test_days=test_days_input)
            st.session_state["backtest_result"] = (bt_metrics, bt_df)

    bt_metrics, bt_df = st.session_state["backtest_result"]

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("策略總報酬率", f"{bt_metrics.total_return:+.2f}%", delta=f"{bt_metrics.total_return - bt_metrics.benchmark_return:+.2f}% vs 大盤")
    with m2:
        st.metric("大盤持有報酬率", f"{bt_metrics.benchmark_return:+.2f}%")
    with m3:
        st.metric("交易勝率", f"{bt_metrics.win_rate:.1f}%", f"{bt_metrics.win_days}勝 / {bt_metrics.loss_days}敗")
    with m4:
        st.metric("盈虧比 (PF)", f"{bt_metrics.profit_factor:.2f}")
    with m5:
        st.metric("最大回撤 (MDD)", f"{bt_metrics.max_drawdown:.2f}%", delta_color="inverse")
    with m6:
        st.metric("夏普值 (Sharpe)", f"{bt_metrics.sharpe_ratio:.2f}")

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Strategy_Equity'], name='本策略淨值 (Strategy)', line=dict(color='#2ca02c', width=2.5)))
    fig_eq.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Benchmark_Equity'], name='大盤買進持有 (Benchmark)', line=dict(color='#7f7f7f', width=1.5, dash='dash')))

    fig_eq.update_layout(
        title=f"策略資金淨值走勢 vs 大盤基準 (近 {bt_metrics.total_days} 個交易日)",
        yaxis_title="資產淨值 (NTD)",
        height=400,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Drawdown'], name='策略回撤 (%)', fill='tozeroy', line=dict(color='#d62728', width=1)))
    fig_dd.update_layout(
        title="策略歷史回撤 (Drawdown %)",
        yaxis_title="回撤幅度 (%)",
        height=220,
        margin=dict(l=40, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_dd, use_container_width=True)


# ================= TAB 6: 每日報告與推播 =================
with tab6:
    st.subheader("📋 每日預測報告生成與即時推播")

    report_md = generate_markdown_report(pred_res)
    st.markdown("### 報告預覽")
    st.markdown(report_md)

    st.divider()
    st.subheader("📥 匯出或發送")
    col_x, col_y = st.columns(2)
    with col_x:
        st.download_button(
            label="💾 下載 Markdown 報告檔 (.md)",
            data=report_md,
            file_name=f"TAIEX_Daily_Report_{pred_res.date}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col_y:
        if st.button("📤 測試發送通知至 Webhook / Line", use_container_width=True):
            if line_token:
                if send_line_notify(line_token, f"\n{report_md}"):
                    st.success("✅ Line Notify 發送成功！")
                else:
                    st.error("❌ Line Notify 發送失敗。")
            if discord_url:
                if send_discord_webhook(discord_url, report_md[:1900]):
                    st.success("✅ Discord Webhook 發送成功！")
                else:
                    st.error("❌ Discord Webhook 發送失敗。")
            if tg_token and tg_chat_id:
                if send_telegram_message(tg_token, tg_chat_id, report_md):
                    st.success("✅ Telegram 發送成功！")
                else:
                    st.error("❌ Telegram 發送失敗。")
            if not (line_token or discord_url or (tg_token and tg_chat_id)):
                st.warning("⚠️ 請先在左側邊欄填入 Line Token、Discord URL 或 Telegram 資訊。")
