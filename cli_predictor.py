"""
cli_predictor.py - 終端機彩色命令列快速預測工具 (含三大法人與期貨籌碼)
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
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from data_fetcher import build_aligned_dataset, get_latest_market_snapshot
from predictor import TAIEXPredictor
from notifier import generate_markdown_report

console = Console()


def run_cli(force_reload: bool = False, export_md: bool = False):
    console.print()
    console.rule("[bold cyan]🇹🇼 台灣加權指數（台股大盤）每日多空預測與籌碼診斷系統[/bold cyan]")
    console.print()

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task1 = progress.add_task("[yellow]正在獲取台股、美股跨市場與三大法人籌碼數據...", total=None)
        raw_df = build_aligned_dataset(period="5y", force_reload=force_reload)
        progress.update(task1, completed=True)

        task2 = progress.add_task("[yellow]計算多因子技術指標、期貨OI與機器學習特徵...", total=None)
        predictor = TAIEXPredictor()
        feats_df = predictor.build_feature_dataframe(raw_df)
        progress.update(task2, completed=True)

        task3 = progress.add_task("[yellow]運行四維度綜合模型與風控點位運算...", total=None)
        result = predictor.predict_latest(feats_df)
        progress.update(task3, completed=True)

    # 1. 跨市場概況表
    snap = get_latest_market_snapshot()
    snap_table = Table(title="🌍 跨市場前導即時盤況", show_header=True, header_style="bold magenta", expand=True)
    snap_table.add_column("市場/標的", justify="left")
    snap_table.add_column("最新價格", justify="right")
    snap_table.add_column("漲跌幅", justify="right")
    snap_table.add_column("日期", justify="center")

    label_map = {
        "TAIEX": "🇹🇼 台灣加權指數",
        "TSMC_ADR": "🇺🇸 台積電 ADR (TSM)",
        "SOX": "🇺🇸 費城半導體 (^SOX)",
        "SP500": "🇺🇸 標普 500 (^GSPC)",
        "NASDAQ": "🇺🇸 那斯達克 (^IXIC)",
        "USDTWD": "💱 美元兌新台幣",
        "TSMC_TW": "🇹🇼 台積電現貨 (2330)"
    }

    for k, name in label_map.items():
        v = snap.get(k)
        if v:
            color = "red" if v["pct_change"] > 0 else "green" if v["pct_change"] < 0 else "white"
            snap_table.add_row(
                name,
                f"{v['close']:,.2f}",
                f"[{color}]{v['pct_change']:+.2f}%[/{color}]",
                v["date"]
            )
    console.print(snap_table)
    console.print()

    # 2. 三大法人與期貨籌碼專屬卡片表
    chips_table = Table(title="🏦 三大法人現貨買賣超與台指期貨未平倉 (OI)", show_header=True, header_style="bold red", expand=True)
    chips_table.add_column("籌碼項目", justify="left")
    chips_table.add_column("數值/金額", justify="right", style="bold")
    chips_table.add_column("狀態解讀", justify="left")

    f_col = "red" if result.foreign_net_buy > 0 else "green" if result.foreign_net_buy < 0 else "white"
    t_col = "red" if result.trust_net_buy > 0 else "green" if result.trust_net_buy < 0 else "white"
    tot_col = "red" if result.total_inst_net_buy > 0 else "green" if result.total_inst_net_buy < 0 else "white"
    oi_col = "red" if result.tx_foreign_net_oi > 0 else "green" if result.tx_foreign_net_oi < -30000 else "yellow"

    f_days = result.foreign_consec_days
    f_str = f"連買 {abs(f_days)} 天" if f_days > 0 else f"連賣 {abs(f_days)} 天" if f_days < 0 else "持平"

    chips_table.add_row("外資現貨買賣超", f"[{f_col}]{result.foreign_net_buy:+.2f} 億[/{f_col}]", f"外資主要流向 ({f_str})")
    chips_table.add_row("投信現貨買賣超", f"[{t_col}]{result.trust_net_buy:+.2f} 億[/{t_col}]", "本土投信與被動 ETF")
    chips_table.add_row("自營商現貨買賣超", f"{result.dealer_net_buy:+.2f} 億", "自營商自行買賣與避險")
    chips_table.add_row("三大法人合計買賣超", f"[{tot_col}]{result.total_inst_net_buy:+.2f} 億[/{tot_col}]", "現貨主力淨買賣總量")
    chips_table.add_row("外資大台期貨未平倉 (OI)", f"[{oi_col}]{result.tx_foreign_net_oi:+,d} 口[/{oi_col}]", f"多空比: {result.tx_foreign_ls_ratio:.2f} ({'空方重度避險' if result.tx_foreign_net_oi < -35000 else '偏多攻擊' if result.tx_foreign_net_oi > 0 else '常態避險'})")

    console.print(chips_table)
    console.print()

    # 3. 核心預測徽章
    if "強力買進" in result.signal:
        badge_style = "bold white on red"
        badge_icon = "🔴🚀"
    elif "偏多" in result.signal:
        badge_style = "bold white on dark_red"
        badge_icon = "📈"
    elif "強力賣出" in result.signal:
        badge_style = "bold white on green"
        badge_icon = "🟢🚨"
    elif "偏空" in result.signal:
        badge_style = "bold white on dark_green"
        badge_icon = "📉"
    else:
        badge_style = "bold black on yellow"
        badge_icon = "⏸️"

    verdict_text = Text()
    verdict_text.append(f"\n {badge_icon}  今日決策建議：{result.signal}\n\n", style=badge_style)
    verdict_text.append(f" • 建議操作：{result.action}\n", style="bold")
    verdict_text.append(f" • 建議持股水位：{result.suggested_position}\n", style="bold cyan")
    verdict_text.append(f" • 大盤昨日收盤：{result.current_close:,.2f} ({result.pct_change:+.2f}%)\n")
    verdict_text.append(f" • AI 模型明日上漲機率：", style="bold")
    
    up_bar = "█" * int(result.prob_up // 5)
    down_bar = "█" * int(result.prob_down // 5)
    verdict_text.append(f"{result.prob_up:.1f}% ", style="bold red" if result.prob_up >= 50 else "bold green")
    verdict_text.append(f"[漲 {up_bar} | 跌 {down_bar}] {result.prob_down:.1f}%\n", style="dim")
    verdict_text.append(f" • 綜合量化多空分數：{result.composite_score:+.1f} / 100 (技術:{result.tech_score:+.0f}, 籌碼:{result.chip_score:+.0f})\n", style="bold yellow")

    console.print(Panel(verdict_text, title=f"[bold]🎯 【{result.date}】加權指數明日多空研判[/bold]", expand=True, border_style="cyan"))
    console.print()

    # 4. 關鍵點位表
    levels_table = Table(title="🛡️ 關鍵支撐壓力與動態風控點位", show_header=True, header_style="bold blue", expand=True)
    levels_table.add_column("指標項目", justify="left")
    levels_table.add_column("點位", justify="center", style="bold")
    levels_table.add_column("策略說明", justify="left")

    levels_table.add_row("預估今日震盪低點", f"{result.expected_low:,.1f}", "日內波動率支撐下緣")
    levels_table.add_row("第一支撐關卡 (S1)", f"{result.support_1:,.1f}", "多方關鍵防守點")
    levels_table.add_row("建議動態停損點", f"[bold green]{result.target_stop_loss:,.1f}[/bold green]", "跌破/突破請務必嚴格執行紀律")
    levels_table.add_row("第一壓力關卡 (R1)", f"{result.resistance_1:,.1f}", "短線反彈遇壓轉折點")
    levels_table.add_row("預估今日震盪高點", f"{result.expected_high:,.1f}", "日內波動率目標上緣")
    levels_table.add_row("目標停利點", f"[bold red]{result.target_take_profit:,.1f}[/bold red]", "波段滿足獲利了結點")

    console.print(levels_table)
    console.print()

    # 5. 指標多空理由表
    diag_table = Table(title="💡 多因子技術與籌碼指標診斷細項", show_header=True, header_style="bold yellow", expand=True)
    diag_table.add_column("指標類別", justify="left", style="bold")
    diag_table.add_column("狀態評定", justify="center")
    diag_table.add_column("分數", justify="right")
    diag_table.add_column("詳細診斷描述", justify="left")

    for d in result.diagnostics:
        c = "red" if d["score"] > 0 else "green" if d["score"] < 0 else "white"
        diag_table.add_row(
            d["category"],
            f"[{c}]{d['status']}[/{c}]",
            f"[{c}]{d['score']:+d}[/{c}]",
            d["desc"]
        )
    console.print(diag_table)
    console.print()

    # 6. 核心原因摘要
    reasons_panel = Text()
    for r in result.reasons:
        reasons_panel.append(f" {r}\n")
    console.print(Panel(reasons_panel, title="[bold]📌 決策核心依據摘要[/bold]", border_style="green", expand=True))
    console.print()

    if export_md:
        md_text = generate_markdown_report(result)
        out_path = f"daily_report_{result.date}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        console.print(f"[bold green]✨ 每日預測報告已成功匯出至: {out_path}[/bold green]\n")

    console.print("[dim]⚠️ 免責聲明：本程式為 AI 量化輔助模型，非投資顧問，實際交易請衡量個人風險承受能力。[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台灣加權指數每日預測終端工具")
    parser.add_argument("--reload", action="store_true", help="強制重新下載最新市場資料")
    parser.add_argument("--export", action="store_true", help="匯出 Markdown 格式日報檔案")
    args = parser.parse_args()

    run_cli(force_reload=args.reload, export_md=args.export)
