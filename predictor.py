"""
predictor.py - 機器學習預測模型、多因子技術共識模型與籌碼決策系統
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    ExtraTreesClassifier
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score

from indicators import calculate_indicators, diagnose_indicators

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    date: str
    current_close: float
    prev_close: float
    change: float
    pct_change: float
    
    # 預測數值
    signal: str                # 強力買進 / 偏多買進 / 觀望盤整 / 偏空減碼 / 強力賣出
    action: str                # 買進 / 賣出 / 觀望
    prob_up: float             # 上漲機率 (0% ~ 100%)
    prob_down: float           # 下跌機率 (0% ~ 100%)
    composite_score: float     # 綜合多空評分 (-100 ~ +100)
    tech_score: float          # 技術面共識評分 (-100 ~ +100)
    chip_score: float          # 籌碼面量化評分 (-100 ~ +100)
    ml_confidence: float       # 機器學習預測信心度 (%)
    
    # 籌碼數據摘要
    foreign_net_buy: float     # 外資買賣超 (億元)
    trust_net_buy: float       # 投信買賣超 (億元)
    dealer_net_buy: float      # 自營商買賣超 (億元)
    total_inst_net_buy: float  # 三大法人合計 (億元)
    tx_foreign_net_oi: int     # 外資台指期未平倉淨口數
    tx_foreign_ls_ratio: float # 外資期貨多空比
    foreign_consec_days: int   # 外資連買(+) / 連賣(-) 天數
    
    # 風控與點位建議
    suggested_position: str    # 建議持股水位 (如: 70% ~ 80%)
    target_stop_loss: float    # 建議動態停損點
    target_take_profit: float  # 建議停利目標
    support_1: float           # 第一支撐位
    support_2: float           # 第二支撐位
    resistance_1: float        # 第一壓力位
    resistance_2: float        # 第二壓力位
    expected_low: float        # 預期當日低點
    expected_high: float       # 預期當日高點
    
    # 診斷與理由
    reasons: list[str]
    diagnostics: list[dict]
    top_features: list[dict]
    model_accuracy: float


class TAIEXPredictor:
    """
    加權指數高精度四維度決策預測器：
    技術面 + 三集成機器學習(RF + HGB + ExtraTrees) + 三大法人現貨與期貨籌碼 + 美股先導
    """
    def __init__(self, n_estimators: int = 150):
        self.rf_model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=6,
            min_samples_leaf=4,
            random_state=42,
            class_weight="balanced"
        )
        self.hgb_model = HistGradientBoostingClassifier(
            max_iter=120,
            max_depth=4,
            min_samples_leaf=8,
            learning_rate=0.08,
            random_state=42,
            class_weight="balanced"
        )
        self.et_model = ExtraTreesClassifier(
            n_estimators=n_estimators,
            max_depth=6,
            min_samples_leaf=4,
            random_state=42,
            class_weight="balanced"
        )
        self.feature_names = []
        self.is_trained = False
        self.last_accuracy = 0.0
        self.feature_importance_df = pd.DataFrame()

    def build_feature_dataframe(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        擴展全套高階特徵：技術指標 + 跨市場前導變數 + 籌碼變動量 + 滯後特徵
        """
        df = calculate_indicators(raw_df)

        # 滯後技術特徵
        lag_cols = [
            "Return_1d", "MACD_OSC", "RSI_14", "K_9", "BB_PercentB",
            "Vol_Ratio_5", "MA_Spread_5_20", "Candle_Body_Ratio"
        ]
        for col in lag_cols:
            if col in df.columns:
                df[f"{col}_lag1"] = df[col].shift(1)
                df[f"{col}_lag2"] = df[col].shift(2)

        # 跨市場 ADR 與美股先導特徵 (隔夜衝擊力)
        cross_cols = ["TSMC_ADR_Return_1d", "SOX_Return_1d", "SP500_Return_1d", "NASDAQ_Return_1d", "USDTWD_Return_1d"]
        for c in cross_cols:
            if c in df.columns:
                df[f"{c}_lag1"] = df[c].shift(1)

        # 籌碼滯後特徵與變化量 (Delta Features)
        if "TX_Foreign_Net_OI" in df.columns:
            df["TX_Foreign_OI_Delta_1d"] = df["TX_Foreign_Net_OI"].diff().fillna(0)
            df["TX_Foreign_OI_Delta_3d"] = df["TX_Foreign_Net_OI"].diff(3).fillna(0)

        chip_cols = [
            "Foreign_Net_Buy", "Trust_Net_Buy", "Dealer_Net_Buy", "Total_Inst_Net_Buy",
            "TX_Foreign_Net_OI", "TX_Foreign_LS_Ratio", "Foreign_Consecutive_Days"
        ]
        for c in chip_cols:
            if c in df.columns:
                df[f"{c}_lag1"] = df[c].shift(1)

        # 星期與月份特徵
        df["DayOfWeek"] = df.index.dayofweek
        df["Month"] = df.index.month

        # 目標變數：隔日漲跌
        df["Target_Next_Return"] = (df["Close"].shift(-1) - df["Close"]) / df["Close"] * 100
        df["Target_Binary"] = (df["Target_Next_Return"] > 0).astype(int)

        return df

    def get_feature_list(self, df: pd.DataFrame) -> list[str]:
        """獲取參與模型訓練的特徵欄位名單"""
        exclude_cols = [
            "Open", "High", "Low", "Close", "Adj Close", "Volume", "TR",
            "Target_Next_Return", "Target_Binary", "Pivot",
            "Resistance_1", "Resistance_2", "Support_1", "Support_2",
            "Bias_120", "Bias_240", "SMA_120", "SMA_240"
        ]
        features = [col for col in df.columns if col not in exclude_cols and not col.startswith("SMA_")]
        return features

    def train(self, df_with_features: pd.DataFrame) -> dict:
        """
        使用歷史數據訓練三重集成機器學習模型 (RF + HGB + ExtraTrees)
        """
        features = self.get_feature_list(df_with_features)
        self.feature_names = features

        clean_df = df_with_features.iloc[60:].copy()
        clean_df[features] = clean_df[features].ffill().bfill().fillna(0)
        
        train_data = clean_df.iloc[:-1].dropna(subset=["Target_Binary"])

        if len(train_data) < 50:
            raise ValueError(f"歷史訓練資料不足（現有 {len(train_data)} 筆，需至少 50 筆）！")

        X = train_data[features].values
        y = train_data["Target_Binary"].values

        n_splits = min(5, len(train_data) // 60)
        tscv = TimeSeriesSplit(n_splits=max(2, n_splits))
        acc_scores = []

        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X[train_idx], X[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]

            rf_temp = RandomForestClassifier(n_estimators=100, max_depth=6, min_samples_leaf=4, random_state=42)
            rf_temp.fit(X_tr, y_tr)
            preds = rf_temp.predict(X_val)
            acc_scores.append(accuracy_score(y_val, preds))

        self.last_accuracy = float(np.mean(acc_scores)) if acc_scores else 0.55

        # 訓練三大集成子模型
        self.rf_model.fit(X, y)
        self.hgb_model.fit(X, y)
        self.et_model.fit(X, y)

        # 整合特徵重要度
        importances = (self.rf_model.feature_importances_ + self.et_model.feature_importances_) / 2.0
        imp_df = pd.DataFrame({
            "feature": features,
            "importance": importances
        }).sort_values(by="importance", ascending=False)
        self.feature_importance_df = imp_df
        self.is_trained = True

        logger.info(f"Ensemble model trained successfully on {len(train_data)} records. CV Accuracy: {self.last_accuracy:.2%}")
        return {
            "cv_accuracy": self.last_accuracy,
            "train_samples": len(train_data),
            "feature_count": len(features),
            "top_features": imp_df.head(10).to_dict(orient="records")
        }

    def predict_latest(self, df_with_features: pd.DataFrame) -> PredictionResult:
        """
        對最新一日進行高精度集成預測與買賣訊號評定
        """
        if not self.is_trained:
            self.train(df_with_features)

        latest_row = df_with_features.iloc[-1]
        prev_row = df_with_features.iloc[-2] if len(df_with_features) >= 2 else latest_row

        close_price = float(latest_row["Close"])
        prev_close = float(prev_row["Close"])
        change = close_price - prev_close
        pct_change = (change / prev_close) * 100

        # 1. 三重機器學習模型加權集成預測機率 (RandomForest 35% + HistGradientBoosting 35% + ExtraTrees 30%)
        X_latest = latest_row[self.feature_names].values.reshape(1, -1)
        X_latest = np.nan_to_num(X_latest, nan=0.0)

        rf_prob = self.rf_model.predict_proba(X_latest)[0]
        hgb_prob = self.hgb_model.predict_proba(X_latest)[0]
        et_prob = self.et_model.predict_proba(X_latest)[0]

        prob_down = float(0.35 * rf_prob[0] + 0.35 * hgb_prob[0] + 0.30 * et_prob[0])
        prob_up = float(0.35 * rf_prob[1] + 0.35 * hgb_prob[1] + 0.30 * et_prob[1])

        # 2. 技術面與籌碼面多因子診斷
        diagnostics = diagnose_indicators(df_with_features)
        
        # 分離技術面分數與籌碼面分數
        tech_score = sum(d["score"] for d in diagnostics if "籌碼" not in d["category"] and "期貨" not in d["category"] and "美股" not in d["category"])
        tech_score = max(min(tech_score, 100), -100)

        chip_score = sum(d["score"] for d in diagnostics if "籌碼" in d["category"] or "期貨" in d["category"])
        chip_score = max(min(chip_score, 100), -100)

        # 3. 綜合評分 (四維度權重：技術 40% + 機器學習 35% + 籌碼 15% + 美股 10%)
        ml_score = (prob_up - 0.5) * 200.0

        adr_ret = float(latest_row.get("TSMC_ADR_Return_1d", 0)) if not np.isnan(latest_row.get("TSMC_ADR_Return_1d", 0)) else 0
        sox_ret = float(latest_row.get("SOX_Return_1d", 0)) if not np.isnan(latest_row.get("SOX_Return_1d", 0)) else 0
        us_lead_score = np.clip((adr_ret * 0.6 + sox_ret * 0.4) * 15, -40, 40)

        composite_score = (0.40 * tech_score) + (0.35 * ml_score) + (0.15 * chip_score) + (0.10 * us_lead_score)
        composite_score = float(np.clip(composite_score, -100, 100))

        # 4. 決策訊號與持股水位判定
        reasons = []
        if composite_score >= 35 or (prob_up >= 0.65 and tech_score >= 15 and chip_score >= 0):
            signal = "強力買進 (Strong Buy)"
            action = "積極加碼 / 買進"
            suggested_position = "80% ~ 100% (高持股水位)"
        elif composite_score >= 10 or (prob_up >= 0.55 and tech_score >= 0):
            signal = "偏多操作 (Buy)"
            action = "逢低佈局 / 買進"
            suggested_position = "60% ~ 80% (偏多持股)"
        elif composite_score <= -35 or (prob_up <= 0.35 and tech_score <= -15 and chip_score <= 0):
            signal = "強力賣出 (Strong Sell)"
            action = "積極避險 / 空手"
            suggested_position = "0% ~ 10% (極低持股或避險)"
        elif composite_score <= -10 or (prob_up <= 0.45 and tech_score < 0):
            signal = "偏空警戒 (Sell)"
            action = "逢高減碼 / 賣出"
            suggested_position = "20% ~ 40% (防禦性持股)"
        else:
            signal = "觀望盤整 (Hold / Neutral)"
            action = "區間操作 / 觀望"
            suggested_position = "40% ~ 60% (中性持股)"

        # 5. 理由條列整理
        if prob_up >= 0.55:
            reasons.append(f"🤖 AI 模型預測明日上漲機率達 {prob_up:.1%}，多方動能佔優勢。")
        elif prob_up <= 0.45:
            reasons.append(f"🤖 AI 模型預測明日下跌機率達 {prob_down:.1%}，防禦避險為上。")
        else:
            reasons.append(f"🤖 AI 模型預測多空勢均力敵 (上漲 {prob_up:.1%} vs 下跌 {prob_down:.1%})。")

        # 籌碼面核心理由
        f_net = float(latest_row.get("Foreign_Net_Buy", 0))
        tx_f_oi = int(latest_row.get("TX_Foreign_Net_OI", -15000))
        f_days = int(latest_row.get("Foreign_Consecutive_Days", 0))
        
        if f_net != 0:
            reasons.append(f"🏦 外資現貨今日買賣超 {f_net:+.1f} 億 (連{'買' if f_days > 0 else '賣'} {abs(f_days)} 天)。")
        if tx_f_oi != 0:
            reasons.append(f"⚔️ 外資台指期未平倉淨部位為 {tx_f_oi:+,d} 口。")

        if not np.isnan(adr_ret) and abs(adr_ret) >= 0.5:
            reasons.append(f"🇺🇸 前夜台積電 ADR 變動 {adr_ret:+.2f}%，費城半導體 {sox_ret:+.2f}%。")

        for d in diagnostics:
            if abs(d["score"]) >= 15:
                reasons.append(f"📊 {d['category']}：{d['desc']}")

        # 6. 點位計算
        atr = float(latest_row.get("ATR_14", close_price * 0.012))
        if np.isnan(atr) or atr == 0:
            atr = close_price * 0.012

        s1 = float(latest_row.get("Support_1", close_price - atr))
        s2 = float(latest_row.get("Support_2", close_price - 2 * atr))
        r1 = float(latest_row.get("Resistance_1", close_price + atr))
        r2 = float(latest_row.get("Resistance_2", close_price + 2 * atr))

        expected_low = round(close_price - 0.75 * atr, 1)
        expected_high = round(close_price + 0.75 * atr, 1)

        if "買進" in action:
            stop_loss = round(close_price - 1.2 * atr, 1)
            take_profit = round(close_price + 1.8 * atr, 1)
        elif "賣出" in action:
            # 偏空/賣出時，多方持股最後防守點位為下檔關鍵支撐破位點（絕不高於現價）
            stop_loss = round(min(close_price - 1.0 * atr, s1), 1)
            take_profit = round(max(close_price + 1.2 * atr, r1), 1)
        else:
            stop_loss = round(s1 - 0.5 * atr, 1)
            take_profit = round(r1 + 0.5 * atr, 1)

        date_str = df_with_features.index[-1].strftime("%Y-%m-%d")

        top_feats = []
        if not self.feature_importance_df.empty:
            top_feats = self.feature_importance_df.head(8).to_dict(orient="records")

        return PredictionResult(
            date=date_str,
            current_close=close_price,
            prev_close=prev_close,
            change=change,
            pct_change=pct_change,
            signal=signal,
            action=action,
            prob_up=prob_up * 100,
            prob_down=prob_down * 100,
            composite_score=composite_score,
            tech_score=tech_score,
            chip_score=chip_score,
            ml_confidence=max(prob_up, prob_down) * 100,
            foreign_net_buy=float(latest_row.get("Foreign_Net_Buy", 0)),
            trust_net_buy=float(latest_row.get("Trust_Net_Buy", 0)),
            dealer_net_buy=float(latest_row.get("Dealer_Net_Buy", 0)),
            total_inst_net_buy=float(latest_row.get("Total_Inst_Net_Buy", 0)),
            tx_foreign_net_oi=int(latest_row.get("TX_Foreign_Net_OI", 0)),
            tx_foreign_ls_ratio=float(latest_row.get("TX_Foreign_LS_Ratio", 1.0)),
            foreign_consec_days=int(latest_row.get("Foreign_Consecutive_Days", 0)),
            suggested_position=suggested_position,
            target_stop_loss=stop_loss,
            target_take_profit=take_profit,
            support_1=round(s1, 1),
            support_2=round(s2, 1),
            resistance_1=round(r1, 1),
            resistance_2=round(r2, 1),
            expected_low=expected_low,
            expected_high=expected_high,
            reasons=reasons,
            diagnostics=diagnostics,
            top_features=top_feats,
            model_accuracy=self.last_accuracy * 100
        )


if __name__ == "__main__":
    from data_fetcher import build_aligned_dataset
    print("Testing TAIEXPredictor with Chip features...")
    raw = build_aligned_dataset(period="3y")
    predictor = TAIEXPredictor()
    feats = predictor.build_feature_dataframe(raw)
    res = predictor.predict_latest(feats)
    print(f"\nPrediction for {res.date}:")
    print(f"Close: {res.current_close:.2f} ({res.pct_change:+.2f}%)")
    print(f"Signal: {res.signal} | Action: {res.action}")
    print(f"Up Prob: {res.prob_up:.1f}% | Down Prob: {res.prob_down:.1f}%")
    print(f"Foreign Net Buy: {res.foreign_net_buy:+.2f} 億 | TX Net OI: {res.tx_foreign_net_oi:+,d} 口")
    print(f"Suggested Position: {res.suggested_position}")
    print("\nReasons:")
    for r in res.reasons:
        print(" -", r)
