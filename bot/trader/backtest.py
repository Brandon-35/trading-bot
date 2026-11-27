"""Backtest on public Binance klines. Per-trade simulation mirrors the planned live exits.

Entry at the close of the signal bar; stop = stop_mult*ATR; half closed at +2R (maker) then stop to breakeven; the rest
trails 2.5*ATR; one position per symbol. Costs: taker 0.05%/side (entry, stop exits), maker 0.02% (TP1 half).
Funding is ignored. A bar that touches both stop and TP1 counts as stopped (pessimistic). Open trades close at the last
close. Survivorship bias: the universe is today's top-volume alts, so past results look better than live will.
"""
import argparse
import json
import os
import statistics
import time
from collections import defaultdict

import httpx

from . import signals as sg

TAKER, MAKER, TP1_R, TRAIL_ATR = 0.0005, 0.0002, 2.0, 2.5
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "klines")
TF_MS = {"1h": 3_600_000, "4h": 14_400_000}


def fetch_klines(symbol: str, tf: str, days: int) -> dict:
    """Public klines paginated 1500 at a time, cached under bot/.cache/klines/ (reused for 12 h)."""
    sid = symbol.split(":")[0].replace("/", "")
    path = os.path.join(CACHE, f"{sid}_{tf}_{days}.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 43200:
        with open(path) as f:
            return json.load(f)
    now = int(time.time() * 1000)
    start, rows = now - days * 86_400_000, []
    while start < now:
        r = httpx.get("https://fapi.binance.com/fapi/v1/klines", timeout=30,
                      params={"symbol": sid, "interval": tf, "startTime": start, "limit": 1500})
        r.raise_for_status()
        part = r.json()
        if not part:
            break
        rows += part
        start = part[-1][0] + TF_MS[tf]
        if len(part) < 1500:
            break
    rows = [r for r in rows if r[0] + TF_MS[tf] <= now]           # closed bars only
    c = sg.to_candles([[float(x) for x in r[:6]] for r in rows])
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump(c, f)
    return c


def simulate(c: dict, btc: dict, signal: str, symbol: str = "") -> list[dict]:
    """All trades of one signal on one symbol. R includes fees; dist = initial stop distance."""
    fn, mult, a = sg.SIGNALS[signal], sg.stop_mult(signal), sg.atr(c)
    n, trades, i = len(c["c"]), [], sg.warm(c)
    while i < n - 1:
        side = fn(c, btc, i)
        if not side:
            i += 1
            continue
        d = 1 if side == "long" else -1
        entry, dist = c["c"][i], mult * a[i]
        stop, tp1, half, ext = entry - d * dist, entry + d * TP1_R * dist, False, entry
        r = -TAKER * entry / dist                                         # entry fee, full size
        j, done = i + 1, False
        while j < n and not done:
            h, l = c["h"][j], c["l"][j]
            hit = l <= stop if d == 1 else h >= stop
            if hit:
                frac = 0.5 if half else 1.0
                r += frac * d * (stop - entry) / dist - frac * TAKER * stop / dist
                done = True
            else:
                if not half and (h >= tp1 if d == 1 else l <= tp1):
                    r += 0.5 * TP1_R - 0.5 * MAKER * tp1 / dist
                    half, stop = True, entry
                ext = max(ext, h) if d == 1 else min(ext, l)
                if half:
                    stop = max(stop, ext - TRAIL_ATR * a[j]) if d == 1 else min(stop, ext + TRAIL_ATR * a[j])
                j += 1
        if not done:                                                     # data ended: close at the last close
            j = n - 1
            frac = 0.5 if half else 1.0
            px = c["c"][j]
            r += frac * d * (px - entry) / dist - frac * TAKER * px / dist
        trades.append({"symbol": symbol, "side": side, "t_in": c["t"][i], "t_out": c["t"][min(j, n - 1)], "r": r})
        i = max(j, i + 1)
    return trades


def stats(trades: list[dict], days: float) -> dict:
    ts = sorted(trades, key=lambda t: t["t_out"])
    rs = [t["r"] for t in ts]
    out = {"trades": len(rs), "trades_per_day": len(rs) / days if days else 0.0}
    if not rs:
        return out | {"win_rate": 0.0, "avg_r": 0.0, "median_r": 0.0, "max_consec_losses": 0, "max_dd_r": 0.0,
                      "half1_avg_r": 0.0, "half2_avg_r": 0.0, "half1_trades": 0, "half2_trades": 0, "by_year": {}}
    run = peak = dd = streak = worst = 0.0
    for x in rs:
        run += x
        peak, dd = max(peak, run), max(dd, peak - run)
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)
    t0, t1 = min(t["t_in"] for t in ts), max(t["t_out"] for t in ts)
    mid = (t0 + t1) / 2
    h1 = [t["r"] for t in ts if t["t_in"] < mid]
    h2 = [t["r"] for t in ts if t["t_in"] >= mid]
    yr = defaultdict(list)
    for t in ts:
        yr[time.strftime("%Y", time.gmtime(t["t_in"] / 1000))].append(t["r"])
    avg = lambda x: sum(x) / len(x) if x else 0.0
    return out | {"win_rate": sum(x > 0 for x in rs) / len(rs), "avg_r": avg(rs), "median_r": statistics.median(rs),
                  "max_consec_losses": int(worst), "max_dd_r": dd, "half1_avg_r": avg(h1), "half2_avg_r": avg(h2),
                  "half1_trades": len(h1), "half2_trades": len(h2),
                  "by_year": {y: {"trades": len(v), "avg_r": avg(v)} for y, v in sorted(yr.items())}}


def run(data: dict, btc: dict, names: list[str], tf: str = "4h", days: float = 720) -> dict:
    """data = {symbol: Candles}. Returns {"name:tf": stats + {"signal","tf"}}."""
    res = {}
    for name in names:
        trades = []
        for s, c in data.items():
            if len(c["c"]) > sg.warm(c) + 10:
                trades += simulate(c, sg.align(c, btc), name, s)
        res[f"{name}:{tf}"] = stats(trades, days) | {"signal": name, "tf": tf}
    return res


def table(res: dict) -> str:
    hdr = f"{'signal':<24}{'n':>5}{'/day':>6}{'win%':>6}{'avgR':>7}{'medR':>7}{'maxL':>5}{'ddR':>7}{'h1 R(n)':>13}{'h2 R(n)':>13}  years"
    rows = [hdr]
    for k, r in res.items():
        yrs = " ".join(f"{y}:{v['avg_r']:+.2f}({v['trades']})" for y, v in r["by_year"].items())
        rows.append(f"{k:<24}{r['trades']:>5}{r['trades_per_day']:>6.2f}{r['win_rate'] * 100:>6.0f}{r['avg_r']:>+7.3f}"
                    f"{r['median_r']:>+7.2f}{r['max_consec_losses']:>5}{r['max_dd_r']:>7.1f}"
                    f"{r['half1_avg_r']:>+8.3f}({r['half1_trades']:>3}){r['half2_avg_r']:>+8.3f}({r['half2_trades']:>3})  {yrs}")
    return "\n".join(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--signal", default="all")
    p.add_argument("--tf", default="4h")
    p.add_argument("--days", type=int, default=720)
    p.add_argument("--symbols", type=int, default=12)
    a = p.parse_args()
    import ccxt
    syms = sg.universe(ccxt.binanceusdm(), a.symbols)
    btc = fetch_klines("BTC/USDT:USDT", a.tf, a.days)
    data = {s: fetch_klines(s, a.tf, a.days) for s in syms}
    names = list(sg.SIGNALS) if a.signal == "all" else [a.signal]
    res = run(data, btc, names, a.tf, a.days)
    print(f"universe ({len(syms)}): {' '.join(s.split('/')[0] for s in syms)}  [survivorship bias; funding ignored]")
    print(table(res))
    path = sg.RESULTS_FILE
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(old | res, f)
    print("gate pass:", sg.best_signal(res))
    return res


if __name__ == "__main__":
    main()
