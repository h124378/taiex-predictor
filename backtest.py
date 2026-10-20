"""
backtest.py - 加權指數策略回測引擎
支援步進式 (Walk-forward / Out-of-sample) 策略模擬與績效評估
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
from dataclasses import dataclass
from typing import Optional

from data_fetcher import build_aligned_dataset
from predictor import TAIEXPredictor


@dataclass
class BacktestMetrics:
    total_return: float         # 策略總報酬率 (%)
    benchmark_return: float     # 大盤買進持有報酬率 (%)
    annualized_return: float    # 年化報酬率 (%)
    win_rate: float             # 交易勝率 (%)
    profit_factor: float        # 盈虧比 (Profit Factor)
    max_drawdown: float         # 最大回撤 MDD (%)
    sharpe_ratio: float         # 夏普值 (Sharpe Ratio)
    total_days: int             # 回測總交易日
    trade_count: int            # 總交易次數
    win_days: int               # 獲利天數
    loss_days: int              # 虧損天數


class StrategyBacktester:
    """
    加權指數回測引擎
    """
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital

    def run_backtest(
        self,
        df_aligned: pd.DataFrame,
        test_days: int = 250,
        retrain_freq: int = 60,
        fee_rate: float = 0.001425 * 0.6 + 0.003  # 手續費打折 + 交易稅
    ) -> tuple[BacktestMetrics, pd.DataFrame]:
        """
        執行滾動步進式回測 (Walk-Forward Backtesting)
        """
        predictor = TAIEXPredictor()
        df_features = predictor.build_feature_dataframe(df_aligned)
        features = predictor.get_feature_list(df_features)

        # 確保資料量足夠
        valid_df = df_features.dropna(subset=features + ["Target_Binary"]).copy()
        total_len = len(valid_df)

        if total_len <= test_days:
            test_days = max(50, total_len // 3)

        start_idx = total_len - test_days

        signals = []
        positions = []      # 0.0 (空手), 0.5 (半倉), 1.0 (全倉)
        prob_ups = []
        tech_scores = []
        daily_rets = []

        # 預先初始化模型
        train_sub = valid_df.iloc[:start_idx]
        predictor.train(train_sub)

        for i in range(start_idx, total_len):
            # 定期重新訓練模型 (適應最新市場環境)
            if (i - start_idx) % retrain_freq == 0 and i > start_idx:
                current_train = valid_df.iloc[:i]
                predictor.train(current_train)

            # 當日數據與特徵
            row = valid_df.iloc[i]
            current_df = valid_df.iloc[:i+1]

            # 預測
            pred_res = predictor.predict_latest(current_df)
            prob_ups.append(pred_res.prob_up)
            tech_scores.append(pred_res.tech_score)
            signals.append(pred_res.signal)

            # 持股部位映射
            if "強力買進" in pred_res.signal:
                pos = 1.0
            elif "偏多" in pred_res.signal:
                pos = 0.8
            elif "觀望" in pred_res.signal:
                pos = 0.3
            elif "偏空" in pred_res.signal:
                pos = 0.0
            else:  # 強力賣出
                pos = 0.0
            positions.append(pos)

        # 組合回測結果表
        backtest_df = valid_df.iloc[start_idx:total_len].copy()
        backtest_df["Signal"] = signals
        backtest_df["Prob_Up"] = prob_ups
        backtest_df["Tech_Score"] = tech_scores
        backtest_df["Position"] = positions

        # 收益計算：隔日收益率 * 當日持股部位
        # 大盤單日收益率
        backtest_df["Market_Return"] = backtest_df["Close"].pct_change().fillna(0)
        
        # 策略隔日收益率 (以當天收盤決定持股，享受隔日報酬)
        backtest_df["Strategy_Return"] = backtest_df["Position"].shift(1).fillna(0) * backtest_df["Market_Return"]

        # 扣除換倉手續費
        pos_change = backtest_df["Position"].diff().abs().fillna(0)
        backtest_df["Strategy_Return_Net"] = backtest_df["Strategy_Return"] - (pos_change * fee_rate)

        # 計算累積淨值曲線 (Equity Curve)
        backtest_df["Benchmark_Equity"] = (1 + backtest_df["Market_Return"]).cumprod() * self.initial_capital
        backtest_df["Strategy_Equity"] = (1 + backtest_df["Strategy_Return_Net"]).cumprod() * self.initial_capital

        # 計算回撤 (Drawdown)
        strat_peak = backtest_df["Strategy_Equity"].cummax()
        backtest_df["Drawdown"] = (backtest_df["Strategy_Equity"] - strat_peak) / strat_peak * 100
        max_dd = float(backtest_df["Drawdown"].min())

        # 績效指標計算
        total_strat_return = float((backtest_df["Strategy_Equity"].iloc[-1] / self.initial_capital - 1) * 100)
        total_bench_return = float((backtest_df["Benchmark_Equity"].iloc[-1] / self.initial_capital - 1) * 100)

        n_days = len(backtest_df)
        ann_return = float(((1 + total_strat_return / 100) ** (252 / max(n_days, 1)) - 1) * 100)

        # 勝率與盈虧比
        active_days = backtest_df[backtest_df["Position"].shift(1) > 0]
        wins = active_days[active_days["Strategy_Return_Net"] > 0]
        losses = active_days[active_days["Strategy_Return_Net"] < 0]

        win_days_count = len(wins)
        loss_days_count = len(losses)
        total_active_days = win_days_count + loss_days_count

        win_rate = (win_days_count / max(total_active_days, 1)) * 100

        total_gain = wins["Strategy_Return_Net"].sum()
        total_loss = abs(losses["Strategy_Return_Net"].sum())
        profit_factor = float(total_gain / (total_loss + 1e-9)) if total_loss > 0 else 1.0

        # 夏普值 (無風險利率設為 1.5%)
        daily_risk_free = (0.015 / 252)
        excess_returns = backtest_df["Strategy_Return_Net"] - daily_risk_free
        std_ret = excess_returns.std()
        sharpe = float((excess_returns.mean() / (std_ret + 1e-9)) * np.sqrt(252)) if std_ret > 0 else 0.0

        # 交易次數 (部位變動次數)
        trades = int((pos_change > 0).sum())

        metrics = BacktestMetrics(
            total_return=round(total_strat_return, 2),
            benchmark_return=round(total_bench_return, 2),
            annualized_return=round(ann_return, 2),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
            total_days=n_days,
            trade_count=trades,
            win_days=win_days_count,
            loss_days=loss_days_count
        )

        return metrics, backtest_df


if __name__ == "__main__":
    print("Testing StrategyBacktester...")
    raw = build_aligned_dataset(period="3y")
    tester = StrategyBacktester()
    metrics, df_res = tester.run_backtest(raw, test_days=200)
    print("\nBacktest Results (Last 200 Trading Days):")
    print(f"Strategy Total Return: {metrics.total_return:+.2f}% vs Benchmark: {metrics.benchmark_return:+.2f}%")
    print(f"Annualized Return: {metrics.annualized_return:+.2f}%")
    print(f"Win Rate: {metrics.win_rate:.1f}% ({metrics.win_days} Wins / {metrics.loss_days} Losses)")
    print(f"Profit Factor: {metrics.profit_factor:.2f}")
    print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
