"""
app_portal.py - 台股量化投資決策總指揮中樞 (All-in-One Master Hub)
一鍵整合四大功能：
1. 🏛️ 加權大盤每日多空預測與三大法人籌碼診斷
2. 📈 主動型 (帶A) 與槓桿正2 (帶L) ETF 動能報酬排行榜
3. 👑 ETF 相對低點淘金與精準打擊建倉系統
4. 🔍 任意自選標的（高股息 / 權值股 / 債券）精準打擊自由診斷機
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

# 頁面配置
st.set_page_config(
    page_title="🇹🇼 台股量化投資決策總指揮中樞 (Master Hub)",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 樣式定義
st.markdown("""
<style>
    .hub-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-radius: 14px;
        padding: 16px 22px;
        color: white;
        margin-bottom: 18px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.25);
    }
    .dip-card {
        background-color: var(--secondary-background-color, #1e293b);
        color: var(--text-color, #f8fafc);
        border-radius: 14px;
        padding: 18px;
        border: 1px solid rgba(56, 189, 248, 0.25);
        box-shadow: 0 4px 10px -1px rgba(0,0,0,0.2);
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
        font-size: 0.88rem;
    }
    .ladder-badge {
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.78rem;
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


# ==============================================================================
# 🔒 端對端安全密碼保護機制 (防止區網未授權連入)
# ==============================================================================
AUTH_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_config.json")

def get_system_password() -> str:
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            import json
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("password", "8888")
        except Exception:
            pass
    return "8888"

def save_system_password(new_pwd: str):
    import json
    with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"password": new_pwd}, f, ensure_ascii=False, indent=2)

def require_authentication():
    if st.session_state.get("authenticated", False):
        return True

    st.markdown("""
    <div style="max-width: 480px; margin: 30px auto 15px auto; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid rgba(99, 102, 241, 0.45); border-radius: 16px; padding: 28px 24px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.4);">
        <div style="font-size: 2.8rem; margin-bottom: 8px;">🔒</div>
        <h2 style="color: #f8fafc; margin-bottom: 6px; font-size: 1.35rem;">台股量化投資決策總指揮中樞</h2>
        <p style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 4px;">
            系統已啟用端對端身分安全驗證保護
        </p>
        <span style="background: rgba(34, 197, 94, 0.15); color: #4ade80; font-size: 0.78rem; padding: 2px 10px; border-radius: 10px; border: 1px solid rgba(34, 197, 94, 0.3);">
            未授權裝置無法查看任何股市資料
        </span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        with st.form("login_form"):
            entered_pwd = st.text_input("專屬密碼 (預設初始為 8888)：", type="password", placeholder="請輸入存取密碼...")
            submit_login = st.form_submit_button("🚀 解鎖進入系統", use_container_width=True, type="primary")

            if submit_login:
                real_pwd = get_system_password()
                if entered_pwd == real_pwd:
                    st.session_state["authenticated"] = True
                    st.success("驗證成功！正在載入全市場量化數據...")
                    st.rerun()
                else:
                    st.error("❌ 密碼錯誤！存取已被拒絕。")

        st.caption("💡 提示：預設初始密碼為 **`8888`**，成功登入後可在左側邊欄隨時自訂新密碼。")

    st.stop()

# 執行安全門禁驗證
require_authentication()



# 快取資料載入
@st.cache_data(ttl=120, show_spinner=False)
def load_master_taiex(force_reload: bool = False):
    try:
        from data_fetcher import build_aligned_dataset, get_latest_market_snapshot
        from predictor import TAIEXPredictor
        df = build_aligned_dataset(period="5y", force_reload=force_reload)
        pred = TAIEXPredictor()
        feats = pred.build_feature_dataframe(df)
        res = pred.predict_latest(feats)
        snap = get_latest_market_snapshot()
        return res, snap, None
    except Exception as e:
        return None, None, str(e)


@st.cache_data(ttl=120, show_spinner=False)
def load_master_momentum_etfs(force_reload: bool = False):
    try:
        from etf_advisory import evaluate_all_etfs
        return evaluate_all_etfs(force_reload=force_reload), None
    except Exception as e:
        return [], str(e)


@st.cache_data(ttl=120, show_spinner=False)
def load_master_dip_etfs(force_reload: bool = False):
    try:
        from etf_advisory_dip import evaluate_all_etfs_dip, get_top_dip_picks
        advs = evaluate_all_etfs_dip(force_reload=force_reload)
        top = get_top_dip_picks(advs, limit=3)
        return advs, top, None
    except Exception as e:
        return [], [], str(e)


# 側邊欄控制
with st.sidebar:
    st.markdown("### 🧭 量化總指揮中樞控制台")
    force_refresh = st.button("🔄 全市場數據即時強制更新", use_container_width=True, type="primary")
    st.divider()

    st.markdown("#### 📑 總指揮中樞四大分頁指南")
    st.markdown("""
    - **Tab 1: 🏛️ 大盤多空預測與籌碼診斷**
    - **Tab 2: 📈 主動與正2 ETF 動能排行榜**
    - **Tab 3: 👑 ETF 低點淘金與精準打擊**
    - **Tab 4: 🔍 任意自選標的自由診斷機**
    """)
    st.divider()

    st.info("💡 **一站式體驗**：所有看板已完整融合於此頁面（Port 8500），直接點擊上方標籤頁即可切換，無需開啟多個視窗或記額外 Port！")
    st.divider()

    with st.expander("🔒 專屬安全密碼管理"):
        st.caption("為確保您的看盤系統不被區網其他人窺探，可在此修改存取密碼：")
        new_pwd_input = st.text_input("輸入新密碼", type="password", key="new_pwd_box")
        if st.button("💾 儲存新密碼", key="btn_save_pwd", use_container_width=True):
            if new_pwd_input.strip():
                save_system_password(new_pwd_input.strip())
                st.success("密碼修改成功！已即刻生效。")
            else:
                st.warning("密碼不可為空！")

        if st.button("🔒 立即鎖定 / 登出", key="btn_logout", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()


# 頂部總指揮橫幅
st.html("""
<div class="hub-header">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:1.6rem;">🧭</span>
                <b style="font-size:1.35rem; letter-spacing:0.5px;">台股量化投資決策總指揮中樞 (Master Hub)</b>
                <span style="background:rgba(99,102,241,0.25); color:#a5b4fc; font-size:0.8rem; padding:3px 10px; border-radius:12px; border:1px solid rgba(99,102,241,0.4);">
                    全功能單一入口
                </span>
            </div>
            <div style="font-size:0.88rem; color:#cbd5e1; margin-top:4px;">
                請直接切換下方四大分頁：🏛️ 大盤多空 ｜ 📈 ETF 動能 ｜ 👑 低點淘金 ｜ 🔍 自選診斷
            </div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
            <span style="background:rgba(34,197,94,0.15); color:#4ade80; border:1px solid rgba(34,197,94,0.3); padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:bold;">
                🟢 總指揮伺服器運作中 (Port 8500)
            </span>
        </div>
    </div>
</div>
""")


# ================= 🌐 5 秒高頻即時國際走勢跑馬燈 =================
@st.fragment(run_every="5s")
def render_live_global_ticker():
    from realtime_global_fetcher import fetch_realtime_global_quotes
    quotes, g_score, g_diag = fetch_realtime_global_quotes()
    now_time = datetime.now().strftime("%H:%M:%S")

    st.html(f"""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border-radius: 12px; padding: 12px 16px; color: white; margin-bottom: 15px; border: 1px solid rgba(99, 102, 241, 0.25);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 10px; height: 10px; background-color: #38bdf8; border-radius: 50%; animation: pulse 1.5s infinite;"></span>
                <b style="font-size: 1.0rem; letter-spacing: 0.5px;">🌐 國際即時走勢與台股先導風向</b>
                <span style="background: #312e81; font-size: 0.72rem; padding: 2px 8px; border-radius: 10px; color: #a5b4fc;">5 秒即時 ⚡</span>
            </div>
            <div style="font-size: 0.82rem; color: #94a3b8;">最後更新: <b style="color: #38bdf8;">{now_time}</b></div>
        </div>
        <div style="background: rgba(255,255,255,0.06); padding: 6px 10px; border-radius: 8px; font-size: 0.85rem;">
            <b>🎯 台股先導多空評估：</b> <span style="color: {'#4ade80' if g_score >= 8 else '#f87171' if g_score <= -8 else '#facc15'}; font-weight:bold;">{g_diag}</span>
            <span style="color:#94a3b8; font-size:0.78rem; margin-left:8px;">(多空權重分: {g_score:+.1f}/100)</span>
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
                <div style="background: var(--secondary-background-color, rgba(255,255,255,0.06)); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 6px; text-align: center;">
                    <div style="font-size: 0.75rem; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{q.name}</div>
                    <div style="font-size: 0.92rem; font-weight: bold; margin: 1px 0;">{q.price:,.2f}</div>
                    <div style="background: {badge_bg}; color: {text_color}; font-weight: bold; font-size: 0.75rem; border-radius: 4px; padding: 1px 4px; display: inline-block;">
                        {sign}{q.pct_change:.2f}%
                    </div>
                </div>
                """)

render_live_global_ticker()


# 四大核心導航分頁 (Master Tabs)
tab_market, tab_momentum, tab_dip, tab_custom = st.tabs([
    "🏛️ 大盤多空預測與籌碼診斷",
    "📈 主動與正2 ETF 動能榜",
    "👑 ETF 低點淘金與精準打擊",
    "🔍 任意自選標的自由診斷機"
])


# ==============================================================================
# TAB 1: 🏛️ 大盤多空預測與籌碼診斷
# ==============================================================================
with tab_market:
    pred_res, snap, err = load_master_taiex(force_reload=force_refresh)
    if err or not pred_res:
        st.warning(f"大盤資料載入中或發生異常: {err}")
    else:
        date_str = pred_res.date
        p_up = pred_res.prob_up
        p_down = pred_res.prob_down
        c_score = getattr(pred_res, "composite_score", 0.0)

        # 頂部快照指標列
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("加權指數收盤", f"{pred_res.current_close:,.2f}", f"{pred_res.change:+,.2f} ({pred_res.pct_change:+.2f}%)")
        with c2:
            st.metric("外資現貨買賣超", f"{pred_res.foreign_net_buy:+.2f} 億", f"連{'買' if pred_res.foreign_consec_days>0 else '賣'}{abs(pred_res.foreign_consec_days)}天")
        with c3:
            st.metric("外資期貨淨留倉", f"{pred_res.tx_foreign_net_oi:+,d} 口", f"多空比 {pred_res.tx_foreign_ls_ratio:.2f}")
        with c4:
            st.metric("三大法人合計現貨", f"{pred_res.total_inst_net_buy:+.2f} 億", f"投信 {pred_res.trust_net_buy:+.1f}億 / 自營 {pred_res.dealer_net_buy:+.1f}億")

        st.write("")

        col_left, col_right = st.columns([1.1, 1.3])
        with col_left:
            # 訊號狀態顏色
            sig_color = "#22c55e" if "買" in pred_res.signal else "#ef4444" if "賣" in pred_res.signal else "#facc15"
            st.html(f"""
            <div style="background: var(--secondary-background-color, #1e293b); border: 2px solid {sig_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.9rem; color:#94a3b8;">觀測基準日：<b>{date_str}</b></span>
                    <span style="background:{sig_color}; color:white; font-weight:800; font-size:1.0rem; padding:4px 12px; border-radius:16px;">
                        {pred_res.signal}
                    </span>
                </div>
                <div style="margin: 12px 0 8px 0;">
                    <div style="font-size:0.85rem; color:#94a3b8;">三重集成預測明日走勢機率：</div>
                    <div style="display:flex; justify-content:space-between; font-weight:800; font-size:1.1rem; margin-top:4px;">
                        <span style="color:#ef4444;">🔴 看多機率: {p_up:.1f}%</span>
                        <span style="color:#22c55e;">🟢 看空機率: {p_down:.1f}%</span>
                    </div>
                    <div style="width:100%; height:12px; background:#22c55e; border-radius:6px; overflow:hidden; display:flex; margin-top:6px;">
                        <div style="width:{p_up}%; background:#ef4444; height:100%;"></div>
                    </div>
                </div>
                <div style="background:rgba(255,255,255,0.05); padding:10px; border-radius:8px; margin-top:10px; font-size:0.88rem;">
                    <div><b>建議整體持股水位：</b> <span style="color:#facc15; font-weight:bold;">{pred_res.suggested_position}</span></div>
                    <div><b>建議具體操作：</b> <span style="color:#f8fafc; font-weight:bold;">{pred_res.action}</span></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:10px; font-size:0.85rem; padding-top:8px; border-top:1px dashed rgba(148,163,184,0.3);">
                    <span>🎯 波段獲利目標: <b style="color:#ef4444;">{pred_res.target_take_profit:,.1f}</b></span>
                    <span>🛑 嚴格停損防守: <b style="color:#22c55e;">{pred_res.target_stop_loss:,.1f}</b></span>
                </div>
            </div>
            """)

            with st.expander("📝 核心決策歸因與籌碼依據", expanded=True):
                for reason in pred_res.reasons:
                    st.markdown(f"- {reason}")

        with col_right:
            # 關鍵點位與籌碼雷達
            st.markdown("#### 🎯 關鍵支撐壓力矩陣")
            k_cols = st.columns(4)
            with k_cols[0]: st.metric("阻力二 (R2)", f"{pred_res.resistance_2:,.1f}")
            with k_cols[1]: st.metric("阻力一 (R1)", f"{pred_res.resistance_1:,.1f}")
            with k_cols[2]: st.metric("支撐一 (S1)", f"{pred_res.support_1:,.1f}")
            with k_cols[3]: st.metric("支撐二 (S2)", f"{pred_res.support_2:,.1f}")

            st.write("")
            st.markdown("#### ⚔️ 籌碼與技術深度評分")
            st.info(f"**三大法人現貨**：外資 {pred_res.foreign_net_buy:+.1f}億, 投信 {pred_res.trust_net_buy:+.1f}億, 自營商 {pred_res.dealer_net_buy:+.1f}億 (合計 {pred_res.total_inst_net_buy:+.1f}億)")
            st.info(f"**台指期留倉**：外資淨未平倉 {pred_res.tx_foreign_net_oi:,} 口 (多空比: {pred_res.tx_foreign_ls_ratio:.2f})")
            st.info(f"**多空評分共識**：綜合評分 {pred_res.composite_score:+.0f}/100 ｜ 技術分 {pred_res.tech_score:+.0f}/100 ｜ 籌碼分 {pred_res.chip_score:+.0f}/100")



# ==============================================================================
# TAB 2: 📈 主動與正2 ETF 動能排行榜
# ==============================================================================
with tab_momentum:
    m_advs, m_err = load_master_momentum_etfs(force_reload=force_refresh)
    if m_err or not m_advs:
        st.warning(f"動能榜資料載入中或發生異常: {m_err}")
    else:
        st.subheader("📈 主動型 (帶A) 與槓桿正2 (帶L) ETF 動能排行")
        st.caption("按日/週/月報酬率、Alpha 超額報酬、夏普值及經理人戰勝大盤勝率全面評估")

        rows = []
        for a in m_advs:
            p = a.perf
            rows.append({
                "代號": p.ticker.replace(".TW", "").replace(".TWO", ""),
                "ETF 名稱": p.name,
                "分類": p.category,
                "收盤價": p.current_price,
                "今日漲幅%": p.pct_change_1d,
                "近1週%": p.return_1w,
                "近1月%": p.return_1m,
                "近3月%": p.return_3m,
                "YTD%": p.return_ytd,
                "1M Alpha%": p.alpha_1m,
                "夏普值": p.sharpe_ratio,
                "波動度%": p.volatility_ann,
                "最大回撤%": p.max_drawdown,
                "勝率%": p.manager_win_rate,
                "均線趨勢": p.ma_trend,
                "建議評估": a.signal.split(" ")[0]
            })
        m_df = pd.DataFrame(rows).sort_values(by="近1月%", ascending=False).reset_index(drop=True)
        m_df.insert(0, "排名", [f"No.{i+1}" for i in range(len(m_df))])

        st.dataframe(
            m_df,
            column_config={
                "排名": st.column_config.TextColumn(width="small"),
                "代號": st.column_config.TextColumn(width="small"),
                "ETF 名稱": st.column_config.TextColumn(width="medium"),
                "收盤價": st.column_config.NumberColumn(format="%.2f"),
                "今日漲幅%": st.column_config.NumberColumn(format="%+.2f%%"),
                "近1週%": st.column_config.NumberColumn(format="%+.2f%%"),
                "近1月%": st.column_config.NumberColumn(format="%+.2f%%"),
                "近3月%": st.column_config.NumberColumn(format="%+.2f%%"),
                "YTD%": st.column_config.NumberColumn(format="%+.2f%%"),
                "1M Alpha%": st.column_config.NumberColumn(format="%+.2f%%", help="相對於大盤之超額報酬"),
                "夏普值": st.column_config.NumberColumn(format="%.2f"),
                "波動度%": st.column_config.NumberColumn(format="%.1f%%"),
                "最大回撤%": st.column_config.NumberColumn(format="%.1f%%"),
                "勝率%": st.column_config.NumberColumn(format="%.1f%%")
            },
            use_container_width=True,
            height=520,
            hide_index=True
        )


# ==============================================================================
# TAB 3: 👑 ETF 低點淘金與精準打擊
# ==============================================================================
with tab_dip:
    d_advs, top_dips, d_err = load_master_dip_etfs(force_reload=force_refresh)
    if d_err or not d_advs:
        st.warning(f"淘金榜資料載入中或發生異常: {d_err}")
    else:
        st.subheader("🎯 今日精選「精準打擊黃金買點」前三檔 ETF")
        st.caption("透過【黃金星等 1~5星】+【指標底背離】+【反轉K線吞噬】+【斐波那契 0.618】+【金字塔三段建倉】極致鎖定")

        col_d1, col_d2, col_d3 = st.columns(3)
        rank_badges = [("🥇 第一名精準打擊", "#facc15"), ("🥈 第二名精準打擊", "#38bdf8"), ("🥉 第三名精準打擊", "#a855f7")]

        for idx, (col, a) in enumerate(zip([col_d1, col_d2, col_d3], top_dips)):
            p = a.perf
            rank_title, border_c = rank_badges[idx]
            c_1d = "#ef4444" if p.pct_change_1d >= 0 else "#22c55e"
            
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
                st.html(f"""<div class="dip-card" style="border-top: 5px solid {border_c};">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <span style="font-weight:800; font-size:1.0rem; color:{border_c};">{rank_title}</span>
    <span style="background:rgba(250,204,21,0.2); color:#facc15; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:12px; border:1px solid #facc15;">
        {a.star_badge}
    </span>
</div>
<h3 style="margin:4px 0 2px 0;">{p.name} <small style="font-size:0.85rem; opacity:0.8;">({p.ticker})</small></h3>
<div style="font-size:0.85rem; opacity:0.85; margin-bottom:8px;">分類: <b>{p.category}</b> ｜ 現價: <b style="font-size:1.15rem; color:#f8fafc;">{p.current_price:.2f} 元</b> <span style="color:{c_1d}; font-weight:bold;">({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)</span></div>

<div style="margin-bottom:8px;">
    <span class="radar-tag" style="border-color:#38bdf8;">型態: <b>{a.reversal_pattern.split(' ')[0]}</b></span>
    <span class="radar-tag" style="border-color:#a855f7;">底背離: <b>{a.divergence_type.split(' ')[0]}</b></span>
    <span class="radar-tag" style="border-color:{prem_color}; color:{prem_color};">折溢: <b>{a.premium_discount_rate:+.2f}%</b></span>
    <span class="radar-tag" style="border-color:#ec4899;">融資: <b>{margin_tag_text}</b></span>
    <span class="radar-tag">布林%B: <b>{a.percent_b:.2f}</b></span>
    <span class="radar-tag">量比: <b>{a.vol_ratio_20*100:.0f}%</b></span>
</div>

<div style="margin: 6px 0;">
    <span class="checklist-tag {chk_bb}">{'✓' if chk_bb=='tag-hit' else '✕'} 布林</span>
    <span class="checklist-tag {chk_vol}">{'✓' if chk_vol=='tag-hit' else '✕'} 窒息量</span>
    <span class="checklist-tag {chk_div}">{'✓' if chk_div=='tag-hit' else '✕'} 背離</span>
    <span class="checklist-tag {chk_pat}">{'✓' if chk_pat=='tag-hit' else '✕'} 反轉K</span>
    <span class="checklist-tag {chk_fib}">{'✓' if chk_fib=='tag-hit' else '✕'} 斐波</span>
    <span class="checklist-tag {chk_wash}">{'✓' if chk_wash=='tag-hit' else '✕'} 洗盤</span>
    <span class="checklist-tag {chk_prem}">{'✓' if chk_prem=='tag-hit' else '✕'} 折溢</span>
</div>

<div class="ladder-box">
    <div style="font-weight:700; font-size:0.85rem; margin-bottom:6px; color:#e2e8f0;">🪜 金字塔分批建倉階梯點位：</div>
    <div class="ladder-step">
        <span class="ladder-badge step-1">① 左側試單 (30%)</span>
        <b>{a.stage1_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-2">② 右側加碼 (40%)</span>
        <b>{a.stage2_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-3">③ 順勢加滿 (30%)</span>
        <b>{a.stage3_price:.2f} 元</b>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:6px; padding-top:6px; border-top:1px dashed rgba(148,163,184,0.2); font-size:0.8rem;">
        <span>🛑 停損: <b style="color:#22c55e;">{a.stop_loss_price:.2f}</b></span>
        <span>🎯 目標: <b style="color:#ef4444;">{a.target_price:.2f}</b></span>
    </div>
</div>
</div>""")

        st.write("")
        st.divider()

        st.subheader("📊 全市場主動型與正2 ETF 淘金總排行")
        dip_rows = []
        for a in d_advs:
            p = a.perf
            dip_rows.append({
                "代號": p.ticker.replace(".TW", "").replace(".TWO", ""),
                "ETF 名稱": p.name,
                "精準星等": a.star_badge.split(" ")[0] + " " + a.star_badge.split(" ")[1],
                "折溢價率%": a.premium_discount_rate,
                "預估淨值": a.etf_nav,
                "收盤價": p.current_price,
                "轉折型態": a.reversal_pattern.split(" ")[0],
                "指標底背離": a.divergence_type.split(" ")[0],
                "融資增減(張)": a.etf_margin_change,
                "淘金分": a.dip_quality_score,
                "布林%B": a.percent_b,
                "量比%": a.vol_ratio_20 * 100,
                "①試單價(30%)": a.stage1_price,
                "②加碼價(40%)": a.stage2_price,
                "🛑停損價": a.stop_loss_price
            })
        d_df = pd.DataFrame(dip_rows).sort_values(by="淘金分", ascending=False).reset_index(drop=True)
        d_df.insert(0, "排名", [f"No.{i+1}" for i in range(len(d_df))])

        st.dataframe(
            d_df,
            column_config={
                "排名": st.column_config.TextColumn(width="small"),
                "代號": st.column_config.TextColumn(width="small"),
                "ETF 名稱": st.column_config.TextColumn(width="medium"),
                "折溢價率%": st.column_config.NumberColumn(format="%+.2f%%"),
                "收盤價": st.column_config.NumberColumn(format="%.2f"),
                "今日漲幅%": st.column_config.NumberColumn(format="%+.2f%%"),
                "淘金分": st.column_config.NumberColumn(format="%.1f"),
                "布林%B": st.column_config.NumberColumn(format="%.2f"),
                "量比%": st.column_config.NumberColumn(format="%.0f%%"),
                "①試單價(30%)": st.column_config.NumberColumn(format="%.2f"),
                "②加碼價(40%)": st.column_config.NumberColumn(format="%.2f"),
                "🛑停損價": st.column_config.NumberColumn(format="%.2f")
            },
            use_container_width=True,
            height=480,
            hide_index=True
        )


# ==============================================================================
# TAB 4: 🔍 任意自選標的自由診斷機
# ==============================================================================
with tab_custom:
    from etf_advisory_dip import diagnose_custom_ticker

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
            if st.button(label, key=f"portal_chip_{sym}", use_container_width=True):
                st.session_state["portal_ticker_query"] = sym
                st.rerun()

    curr_pq = st.session_state.get("portal_ticker_query", "00878")

    col_in, col_act = st.columns([4, 1])
    with col_in:
        user_target = st.text_input("輸入股票代碼、ETF 代碼或中文名稱：", value=curr_pq, key="portal_ticker_box", placeholder="例如 00878, 00919, 2330, 鴻海, 0050...")
    with col_act:
        st.write("")
        run_portal_diag = st.button("🚀 啟動精準打擊診斷", key="btn_run_portal_diag", use_container_width=True, type="primary")

    active_symbol = user_target.strip() if user_target.strip() else curr_pq

    if active_symbol:
        with st.spinner(f"正在全維度診斷【{active_symbol}】之底背離、K線反轉、斐波那契、融資清洗與金字塔點位..."):
            c_adv, c_df, c_msg = diagnose_custom_ticker(active_symbol)

        if c_adv and c_df is not None:
            p = c_adv.perf
            c_1d = "#ef4444" if p.pct_change_1d >= 0 else "#22c55e"
            
            chk_bb = "tag-hit" if c_adv.percent_b <= 0.30 else "tag-miss"
            chk_vol = "tag-hit" if c_adv.vol_ratio_20 <= 0.70 else "tag-miss"
            chk_div = "tag-hit" if "背離" in c_adv.divergence_type and "無" not in c_adv.divergence_type else "tag-miss"
            chk_pat = "tag-hit" if "吞噬" in c_adv.reversal_pattern or "晨星" in c_adv.reversal_pattern or "W底" in c_adv.reversal_pattern or c_adv.lower_shadow_ratio >= 30 else "tag-miss"
            chk_fib = "tag-hit" if c_adv.is_fib_confluence or "守穩" in c_adv.trend_alignment else "tag-miss"
            chk_wash = "tag-hit" if c_adv.etf_margin_change < 0 or c_adv.margin_maint_ratio <= 158 else "tag-miss"
            chk_vix = "tag-hit" if "見頂" in c_adv.vix_status or "極度恐慌" in c_adv.vix_status or c_adv.vix_value >= 21 else "tag-miss"
            chk_prem = "tag-hit" if c_adv.premium_discount_rate <= 0.50 else "tag-miss"
            chk_deriv = "tag-hit" if c_adv.taifex_pc_ratio <= 75.0 or c_adv.foreign_futures_oi_change >= 2000 else "tag-miss"

            margin_tag_text = f"{'+' if c_adv.etf_margin_change > 0 else ''}{c_adv.etf_margin_change}張" if c_adv.etf_margin_change != 0 else "籌碼穩定"
            prem_color = "#4ade80" if c_adv.premium_discount_rate < -0.10 else "#f87171" if c_adv.premium_discount_rate > 0.80 else "#38bdf8"
            border_c = "#facc15" if c_adv.golden_stars >= 4 else "#38bdf8" if c_adv.golden_stars >= 3 else "#94a3b8"

            col_res1, col_res2 = st.columns([1.1, 1.3])
            with col_res1:
                st.html(f"""<div class="dip-card" style="border-top: 5px solid {border_c}; background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <span style="font-weight:800; font-size:1.1rem; color:{border_c};">🎯 自選標的精準打擊診斷結果</span>
    <span style="background:rgba(250,204,21,0.2); color:#facc15; font-weight:800; font-size:0.9rem; padding:4px 12px; border-radius:12px; border:1px solid #facc15;">
        {c_adv.star_badge}
    </span>
</div>
<h2 style="margin:6px 0 2px 0;">{p.name} <small style="font-size:0.9rem; opacity:0.8;">({p.ticker})</small></h2>
<div style="font-size:0.9rem; opacity:0.85; margin-bottom:10px;">分類: <b>{p.category}</b> ｜ 現價: <b style="font-size:1.3rem; color:#f8fafc;">{p.current_price:.2f} 元</b> <span style="color:{c_1d}; font-weight:bold;">({'+' if p.pct_change_1d > 0 else ''}{p.pct_change_1d:.2f}%)</span></div>

<div style="margin-bottom:10px;">
    <span class="radar-tag" style="border-color:#38bdf8;">轉折型態: <b>{c_adv.reversal_pattern}</b></span>
    <span class="radar-tag" style="border-color:#a855f7;">底背離: <b>{c_adv.divergence_type}</b></span>
    <span class="radar-tag" style="border-color:{prem_color}; color:{prem_color};">折溢價: <b>{c_adv.premium_discount_rate:+.2f}%</b></span>
    <span class="radar-tag" style="border-color:#ec4899;">融資增減: <b>{margin_tag_text}</b></span>
    <span class="radar-tag" style="border-color:#f43f5e;">VIX: <b>{c_adv.vix_value:.1f}</b></span>
    <span class="radar-tag" style="border-color:#38bdf8;">P/C: <b>{c_adv.taifex_pc_ratio:.1f}%</b></span>
    <span class="radar-tag">布林%B: <b>{c_adv.percent_b:.2f}</b></span>
    <span class="radar-tag">量比: <b>{c_adv.vol_ratio_20*100:.0f}%</b></span>
    <span class="radar-tag">斐波0.618: <b>{c_adv.fib_0618:.2f}</b></span>
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
        <b style="font-size:1.05rem;">{c_adv.stage1_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-2">第 2 批 (右側加碼 40%)</span>
        <b style="font-size:1.05rem;">{c_adv.stage2_price:.2f} 元</b>
    </div>
    <div class="ladder-step">
        <span class="ladder-badge step-3">第 3 批 (順勢加滿 30%)</span>
        <b style="font-size:1.05rem;">{c_adv.stage3_price:.2f} 元</b>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:8px; padding-top:8px; border-top:1px dashed rgba(148,163,184,0.3); font-size:0.85rem;">
        <span>🛑 嚴格停損: <b style="color:#22c55e; font-size:0.95rem;">{c_adv.stop_loss_price:.2f} 元</b></span>
        <span>🎯 波段目標: <b style="color:#ef4444; font-size:0.95rem;">{c_adv.target_price:.2f} 元</b></span>
    </div>
</div>

<div style="background:rgba(148,163,184,0.12); padding:10px 12px; border-radius:6px; font-size:0.83rem; line-height:1.5; margin-top:8px;">
    <b>💡 打擊研判依據：</b><br>
    {'<br>'.join(['• ' + r for r in c_adv.reasons[:4]])}
</div>
</div>""")

            with col_res2:
                clean_cd = p.ticker.replace(".TW", "").replace(".TWO", "").strip()
                p_df = c_df.tail(60).copy()
                rm = p_df["Close"].rolling(20).mean()
                rs = p_df["Close"].rolling(20).std()
                bu = rm + 2 * rs
                bl = rm - 2 * rs

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=p_df.index.strftime("%m-%d"),
                    open=p_df["Open"], high=p_df["High"], low=p_df["Low"], close=p_df["Close"],
                    name="K線",
                    increasing_line_color="#ef4444", decreasing_line_color="#22c55e"
                ))
                fig.add_trace(go.Scatter(x=p_df.index.strftime("%m-%d"), y=rm, line=dict(color="#facc15", width=1.5), name="20MA月線"))
                fig.add_trace(go.Scatter(x=p_df.index.strftime("%m-%d"), y=bu, line=dict(color="rgba(148, 163, 184, 0.4)", width=1, dash="dash"), name="布林上軌"))
                fig.add_trace(go.Scatter(x=p_df.index.strftime("%m-%d"), y=bl, line=dict(color="#38bdf8", width=1.5), name="布林下軌"))

                fig.add_hline(y=c_adv.stage1_price, line_dash="dot", line_color="#38bdf8", annotation_text=f"①試單 {c_adv.stage1_price}", annotation_position="top left")
                fig.add_hline(y=c_adv.stage2_price, line_dash="dot", line_color="#22c55e", annotation_text=f"②加碼 {c_adv.stage2_price}", annotation_position="top left")
                fig.add_hline(y=c_adv.stop_loss_price, line_dash="dash", line_color="#ef4444", annotation_text=f"🛑停損 {c_adv.stop_loss_price}", annotation_position="bottom left")

                fig.update_layout(
                    title=f"📊 {p.name} ({clean_cd}) 近期走勢與金字塔關鍵防守/建倉線",
                    xaxis_rangeslider_visible=False,
                    height=480,
                    margin=dict(l=20, r=20, t=40, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(c_msg)
