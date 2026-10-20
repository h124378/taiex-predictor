"""
cli_etf.py - 終端機命令列工具（精簡版）：今日推薦前三檔、每日報酬率排行榜、每月報酬率排行榜
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from etf_advisory import evaluate_all_etfs, ETFAdvisory, get_top_picks
from realtime_news_fetcher import get_latest_financial_news

console = Console()


def run_etf_cli(force_reload: bool = False):
    console.print()
    console.rule("[bold cyan]🇹🇼 台股主動型 (帶A) 與正2 (帶L) ETF 每日與每月報酬排行榜[/bold cyan]")
    console.print()

    # 顯示即時財經快訊
    try:
        news_items = get_latest_financial_news(force_refresh=False, max_count=5)
        if news_items:
            news_text = Text()
            for n in news_items:
                s_color = "bold green" if n.sentiment == "利多" else "bold red" if n.sentiment == "利空" else "bold white"
                news_text.append(f"• [{n.published_time}] ", style="dim")
                news_text.append(f"[{n.sentiment}] ", style=s_color)
                news_text.append(f"【{','.join(n.tags)}】 ", style="cyan")
                news_text.append(f"{n.title} ", style="white")
                news_text.append(f"({n.source})\n", style="dim")
            console.print(Panel(news_text, title="[bold red]📢 全球與台股重大即時財經快訊[/bold red]", border_style="red", expand=True))
            console.print()
    except Exception:
        pass

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[yellow]正在載入最新成交行情與計算多週期報酬...", total=None)
        advisories = evaluate_all_etfs(force_reload=force_reload)
        progress.update(task, completed=True)

    if not advisories:
        console.print("[bold red]無法獲取 ETF 數據，請檢查網路連線。[/bold red]")
        return

    date_str = advisories[0].perf.date

    # 🧭 整體台股多空勝率與風向預測
    try:
        from data_fetcher import build_aligned_dataset
        from predictor import TAIEXPredictor
        raw_df = build_aligned_dataset(period="5y", force_reload=force_reload)
        predictor = TAIEXPredictor()
        feats_df = predictor.build_feature_dataframe(raw_df)
        taiex_res = predictor.predict_latest(feats_df)
        
        p_up = taiex_res.prob_up
        p_down = taiex_res.prob_down
        dir_style = "bold red" if p_up >= 55 else "bold green" if p_down >= 55 else "bold yellow"
        dir_text = "🔥 看多偏多格局" if p_up >= 55 else "❄️ 看空防禦格局" if p_down >= 55 else "⚖️ 區間震盪盤整"
        
        m_text = Text()
        m_text.append(f"• 大盤風向評估: {dir_text}  ｜  建議策略: {taiex_res.action} (建議水位: {taiex_res.suggested_position})\n", style=dir_style)
        m_text.append(f"• 多空勝率對比: 🔴 看多上漲勝率 {p_up:.1f}%  vs  🟢 看空下跌機率 {p_down:.1f}%\n", style="bold white")
        m_text.append(f"• 指數基準收盤: {taiex_res.current_close:,.2f} ({taiex_res.pct_change:+.2f}%)  ｜  模型準確率: {taiex_res.model_accuracy:.1f}%\n", style="dim")
        m_text.append(f"• 多因子評分表: 綜合量化 {taiex_res.composite_score:+.1f}  ｜  技術面 {taiex_res.tech_score:+.0f}  ｜  籌碼面 {taiex_res.chip_score:+.0f}  ｜  大盤動態停損: {taiex_res.target_stop_loss:,.1f}\n", style="cyan")
        
        console.print(Panel(m_text, title=f"[bold cyan]🧭 【{taiex_res.date}】整體台股加權指數多空勝率預測[/bold cyan]", border_style="cyan", expand=True))
        console.print()
    except Exception:
        pass

    # 1. 🎯 量化精選推薦前三檔 (防高檔追高)
    top_picks = get_top_picks(advisories, limit=3)
    top3_text = Text()
    rank_icons = ["🥇 第一名推薦", "🥈 第二名推薦", "🥉 第三名推薦"]
    for idx, a in enumerate(top_picks):
        p = a.perf
        bias_style = "bold red" if 0.0 <= p.bias_20 <= 2.2 else "bold green" if p.bias_20 > 4.0 else "yellow"
        bias_tag = "🎯 守穩起漲區" if 0.0 <= p.bias_20 <= 2.2 else "⚠️ 乖離偏高" if p.bias_20 > 4.0 else "💎 負乖離" if p.bias_20 < 0 else "溫和"
        
        top3_text.append(f"\n{rank_icons[idx]}：【{p.name} ({p.ticker})】 ── [{bias_tag}]\n", style="bold yellow")
        top3_text.append(f"   • 現價: {p.current_price:.2f} 元  |  今日漲跌: {p.change:+.2f} ({p.pct_change_1d:+.2f}%)  |  近1月累積: {p.return_1m:+.2f}%\n", style="bold red" if p.pct_change_1d >= 0 else "bold green")
        top3_text.append(f"   • 月線乖離: ", style="cyan")
        top3_text.append(f"{p.bias_20:+.2f}%  ", style=bias_style)
        top3_text.append(f"|  KD: ({p.k_9:.1f}, {p.d_9:.1f})  |  RSI: {p.rsi_14:.1f}  |  經理人勝率: {p.manager_win_rate:.1f}%\n", style="cyan")
        top3_text.append(f"   • 建議停損: {a.target_stop_loss:.2f}  |  目標停利: {a.target_take_profit:.2f}  |  操作建議: {a.signal.split(' ')[0]}\n", style="magenta")
        top3_text.append(f"   • 核心理由: {' ｜ '.join(a.reasons[:2])}\n", style="white")

    console.print(Panel(top3_text, title=f"[bold gold1]🎯 【{date_str}】今日量化精選推薦前三檔 ETF (健全防追高買點)[/bold gold1]", border_style="gold1", expand=True))
    console.print()

    # 2. 🏆 每日報酬率排行榜 (今日漲幅 Top)
    daily_sorted = sorted(advisories, key=lambda x: x.perf.pct_change_1d, reverse=True)
    daily_table = Table(title=f"🏆 【{date_str}】每日報酬率排行榜 (今日漲幅 Top 15)", show_header=True, header_style="bold magenta", expand=True)
    daily_table.add_column("排名", justify="center", style="bold")
    daily_table.add_column("代號", justify="center")
    daily_table.add_column("ETF 名稱", justify="left", style="bold")
    daily_table.add_column("類別", justify="center")
    daily_table.add_column("收盤價", justify="right")
    daily_table.add_column("今日漲跌", justify="right")
    daily_table.add_column("今日漲幅%", justify="right", style="bold")
    daily_table.add_column("月線乖離%", justify="right", style="bold")
    daily_table.add_column("近1週%", justify="right")
    daily_table.add_column("近1月%", justify="right")
    daily_table.add_column("操作建議", justify="center")

    for i, a in enumerate(daily_sorted[:15]):
        p = a.perf
        c_1d = "red" if p.pct_change_1d > 0 else "green" if p.pct_change_1d < 0 else "white"
        c_1m = "red" if p.return_1m > 0 else "green" if p.return_1m < 0 else "white"
        c_bias = "yellow" if 0.0 <= p.bias_20 <= 2.2 else "red" if p.bias_20 > 4.0 else "white"
        sig_color = "bold red" if "買進" in a.signal else "yellow" if "觀望" in a.signal else "bold green"
        daily_table.add_row(
            f"No.{i+1}",
            p.ticker.replace(".TW", "").replace(".TWO", ""),
            p.name,
            p.category,
            f"{p.current_price:.2f}",
            f"{p.change:+.2f}",
            f"[{c_1d}]{p.pct_change_1d:+.2f}%[/{c_1d}]",
            f"[{c_bias}]{p.bias_20:+.2f}%[/{c_bias}]",
            f"{p.return_1w:+.2f}%",
            f"[{c_1m}]{p.return_1m:+.2f}%[/{c_1m}]",
            f"[{sig_color}]{a.signal.split(' ')[0]}[/{sig_color}]"
        )
    console.print(daily_table)
    console.print()

    # 3. 🚀 每月報酬率排行榜 (近1月累積報酬 Top)
    monthly_sorted = sorted(advisories, key=lambda x: x.perf.return_1m, reverse=True)
    monthly_table = Table(title=f"🚀 【{date_str}】每月報酬率排行榜 (近1月累積報酬 Top 15)", show_header=True, header_style="bold blue", expand=True)
    monthly_table.add_column("排名", justify="center", style="bold")
    monthly_table.add_column("代號", justify="center")
    monthly_table.add_column("ETF 名稱", justify="left", style="bold")
    monthly_table.add_column("類別", justify="center")
    monthly_table.add_column("收盤價", justify="right")
    monthly_table.add_column("近1月累積%", justify="right", style="bold")
    monthly_table.add_column("月線乖離%", justify="right", style="bold")
    monthly_table.add_column("今日漲幅%", justify="right")
    monthly_table.add_column("經理人勝率%", justify="right", style="bold")
    monthly_table.add_column("經理人Alpha", justify="right", style="bold")
    monthly_table.add_column("操作建議", justify="center")

    for i, a in enumerate(monthly_sorted[:15]):
        p = a.perf
        c_1d = "red" if p.pct_change_1d > 0 else "green" if p.pct_change_1d < 0 else "white"
        c_1m = "red" if p.return_1m > 0 else "green" if p.return_1m < 0 else "white"
        c_win = "red" if p.manager_win_rate >= 50 else "yellow"
        c_alp = "red" if p.alpha_1m > 0 else "green" if p.alpha_1m < 0 else "white"
        c_bias = "yellow" if 0.0 <= p.bias_20 <= 2.2 else "red" if p.bias_20 > 4.0 else "white"
        sig_color = "bold red" if "買進" in a.signal else "yellow" if "觀望" in a.signal else "bold green"
        monthly_table.add_row(
            f"No.{i+1}",
            p.ticker.replace(".TW", "").replace(".TWO", ""),
            p.name,
            p.category,
            f"{p.current_price:.2f}",
            f"[{c_1m}]{p.return_1m:+.2f}%[/{c_1m}]",
            f"[{c_bias}]{p.bias_20:+.2f}%[/{c_bias}]",
            f"[{c_1d}]{p.pct_change_1d:+.2f}%[/{c_1d}]",
            f"[{c_win}]{p.manager_win_rate:.1f}%[/{c_win}]",
            f"[{c_alp}]{p.alpha_1m:+.2f}%[/{c_alp}]",
            f"[{sig_color}]{a.signal.split(' ')[0]}[/{sig_color}]"
        )
    console.print(monthly_table)
    console.print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台股主動型與正2 ETF 每日與每月報酬排行榜")
    parser.add_argument("--reload", action="store_true", help="強制重新下載最新行情數據")
    args = parser.parse_args()

    run_etf_cli(force_reload=args.reload)
