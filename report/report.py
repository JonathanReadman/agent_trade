import os
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.db import DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))


@dataclass
class TradeRecord:
    ticker: str
    action: str
    confidence: float
    signal_price: float
    execution_price: float
    position_size_usd: float
    reasoning: str
    timestamp: str
    pnl_pct: float = 0.0


@dataclass
class ReportMetrics:
    total_trades: int
    win_rate: float
    avg_gain_pct: float
    avg_loss_pct: float
    sharpe_ratio: object  # float or None
    portfolio_pnl_pct: float
    spy_pnl_pct: float
    trades: list
    snapshots: list


def compute_metrics(db_path: str = DEFAULT_DB_PATH,
                    starting_capital: float = STARTING_CAPITAL) -> ReportMetrics:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    trade_rows = conn.execute("""
        SELECT ticker, action, confidence, signal_price, execution_price,
               position_size_usd, reasoning, timestamp
        FROM trades
        WHERE status = 'executed' AND action IN ('BUY', 'SELL')
              AND execution_price IS NOT NULL AND signal_price IS NOT NULL
    """).fetchall()

    snapshot_rows = conn.execute("""
        SELECT date, total_value_usd, cash_usd, spy_close
        FROM portfolio_snapshots ORDER BY date
    """).fetchall()
    conn.close()

    trades = []
    gains, losses = [], []
    for row in trade_rows:
        pnl_pct = ((row["execution_price"] - row["signal_price"]) / row["signal_price"] * 100
                   if row["action"] == "BUY" else
                   (row["signal_price"] - row["execution_price"]) / row["signal_price"] * 100)
        t = TradeRecord(
            ticker=row["ticker"], action=row["action"],
            confidence=row["confidence"], signal_price=row["signal_price"],
            execution_price=row["execution_price"],
            position_size_usd=row["position_size_usd"],
            reasoning=row["reasoning"], timestamp=row["timestamp"],
            pnl_pct=round(pnl_pct, 4),
        )
        trades.append(t)
        if pnl_pct > 0:
            gains.append(pnl_pct)
        else:
            losses.append(pnl_pct)

    total = len(trades)
    win_rate = len(gains) / total if total > 0 else 0.0
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    snapshots = [dict(s) for s in snapshot_rows]
    portfolio_pnl_pct = 0.0
    spy_pnl_pct = 0.0
    sharpe = None
    if snapshots:
        latest = snapshots[-1]
        portfolio_pnl_pct = (latest["total_value_usd"] - starting_capital) / starting_capital * 100
        first_spy = snapshots[0].get("spy_close")
        last_spy = latest.get("spy_close")
        if first_spy and last_spy and first_spy > 0:
            spy_pnl_pct = (last_spy - first_spy) / first_spy * 100

        if len(snapshots) > 1:
            daily_returns = []
            for i in range(1, len(snapshots)):
                prev = snapshots[i - 1]["total_value_usd"]
                curr = snapshots[i]["total_value_usd"]
                if prev > 0:
                    daily_returns.append((curr - prev) / prev)
            if daily_returns:
                import statistics
                mean_r = statistics.mean(daily_returns)
                std_r = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
                sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else None

    return ReportMetrics(
        total_trades=total,
        win_rate=round(win_rate, 4),
        avg_gain_pct=round(avg_gain, 4),
        avg_loss_pct=round(avg_loss, 4),
        sharpe_ratio=round(sharpe, 3) if sharpe is not None else None,
        portfolio_pnl_pct=round(portfolio_pnl_pct, 4),
        spy_pnl_pct=round(spy_pnl_pct, 4),
        trades=sorted(trades, key=lambda t: t.pnl_pct, reverse=True),
        snapshots=snapshots,
    )


def generate_report(output_path: str = "report.html",
                    db_path: str = DEFAULT_DB_PATH) -> None:
    metrics = compute_metrics(db_path=db_path)
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template.html")
    html = template.render(
        metrics=metrics,
        snapshots_json=json.dumps(metrics.snapshots),
        trades_json=json.dumps([
            {"ticker": t.ticker, "confidence": t.confidence, "pnl_pct": t.pnl_pct}
            for t in metrics.trades
        ]),
    )
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    generate_report()
