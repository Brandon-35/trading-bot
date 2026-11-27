"""Arena table from one or more bot databases: python -m trader.report data/*.db"""
import sys

from .store import Store


def stats(path: str) -> dict:
    st = Store(path)
    trades = st.all("trade_close")
    calls = st.all("llm_call")
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [-t["pnl"] for t in trades if t["pnl"] <= 0]
    eq = [e["equity"] for e in st.all("equity")]
    peak, dd = 0.0, 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak if peak else 0)
    cost = sum(c.get("cost") or 0 for c in calls)
    net = sum(t["pnl"] for t in trades) - cost
    gross_loss = sum(losses) + cost
    return {"db": path, "model": calls[-1]["model"] if calls else "-", "trades": len(trades),
            "win_rate": len(wins) / len(trades) if trades else 0, "net_pnl": net,
            "profit_factor": sum(wins) / gross_loss if gross_loss else float("inf") if wins else 0,
            "max_dd": dd, "llm_cost": cost, "llm_errors": sum("error" in c for c in calls),
            "equity": eq[-1] if eq else None}


if __name__ == "__main__":
    print("| model | trades | win % | PF (net of fees + LLM) | net PnL | max DD | LLM $ | LLM errors |")
    print("|---|---|---|---|---|---|---|---|")
    for p in sys.argv[1:]:
        s = stats(p)
        print(f"| {s['model']} | {s['trades']} | {s['win_rate']:.0%} | {s['profit_factor']:.2f} | "
              f"{s['net_pnl']:+.2f} | {s['max_dd']:.1%} | {s['llm_cost']:.2f} | {s['llm_errors']} |")
