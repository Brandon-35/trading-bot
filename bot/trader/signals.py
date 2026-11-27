"""Deterministic signal engine: universe, closed-bar candles, signals, derivatives store, crowding filter.

Candles = {"t","o","h","l","c","v"} lists (t = open time ms). Every signal is evaluated on CLOSED bar i only.
"""
import json
import os
import statistics
import time
from bisect import bisect_right

from .market import rsi

EDGE_GATE = {"min_avg_r": 0.10, "min_trades": 150}
RESULTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "backtest_results.json")
STOP_MULT = {"squeeze": 2.0}          # per-signal stop multiplier in ATR, default 2
DEFAULT_STOP_MULT = 2.0
NON_CRYPTO = {"XAU", "XAG", "NVDA", "TSLA", "SOXL", "SOXS", "SPY", "QQQ", "AAPL", "MSFT", "COIN", "MSTR", "HOOD",
              "AMZN", "GOOGL", "META", "PAXG", "CRCL", "INTC", "AMD", "PLTR"}
REGIME_ONLY = {"BTC", "ETH"}
_uni: dict = {}


def stop_mult(signal: str) -> float:
    return STOP_MULT.get(signal, DEFAULT_STOP_MULT)


# ---------- indicators (full causal series, cached on the candle dict) ----------
def _ema(x: list[float], n: int) -> list[float]:
    k, out = 2 / (n + 1), [x[0]]
    for v in x[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr(c: dict, n: int = 14) -> list[float]:
    """Simple average of the true range over n bars (same definition as market.atr); early bars use what exists."""
    h, l, cl = c["h"], c["l"], c["c"]
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - cl[i - 1]), abs(l[i] - cl[i - 1])) for i in range(1, len(cl))]
    out, s = [], 0.0
    for i, v in enumerate(tr):
        s += v
        if i >= n:
            s -= tr[i - n]
        out.append(s / min(i + 1, n))
    return out


def _ind(c: dict, key, fn):
    x = c.setdefault("_x", {})
    if key not in x:
        x[key] = fn()
    return x[key]


def _k(c: dict) -> int:
    """Bars per 4h, so '1d trend' periods scale with the timeframe."""
    return max(1, round(14_400_000 / (c["t"][1] - c["t"][0])))


def _roll(c, key, src, n, fn):
    """Series where [i] = fn(src[i-n:i]) (previous n bars, current bar excluded)."""
    s = c[src]
    return _ind(c, key, lambda: [fn(s[max(0, i - n):i]) if i else s[0] for i in range(len(s))])


def _bandwidth(c):
    cl = c["c"]
    def f():
        out = []
        for i in range(len(cl)):
            w = cl[max(0, i - 19):i + 1]
            m = sum(w) / len(w)
            out.append(4 * statistics.pstdev(w) / m if len(w) > 1 else 1.0)
        return out
    return _ind(c, "bw", f)


def align(c: dict, btc: dict) -> dict:
    """BTC candles re-indexed so btc[i] is the BTC bar open at c['t'][i] (or the latest earlier one)."""
    idx = [max(0, bisect_right(btc["t"], t) - 1) for t in c["t"]]
    return {k: [btc[k][j] for j in idx] for k in ("t", "o", "h", "l", "c", "v")}


def warm(c: dict) -> int:
    return 300 * _k(c) + 2


def _btc_trend(btc, i):
    """(direction, strength, slope_agrees): BTC close vs EMA300 (4h-equivalent proxy for the 1d trend)."""
    k = _k(btc)
    e = _ind(btc, "ema300", lambda: _ema(btc["c"], 300 * k))
    d = 1 if btc["c"][i] > e[i] else -1
    return d, abs(btc["c"][i] / e[i] - 1), (e[i] - e[max(0, i - 6 * k)]) * d > 0


def _vol_ratio(c, i):
    m = _roll(c, "vm20", "v", 20, lambda w: sum(w) / len(w))[i]
    return c["v"][i] / m if m else 0.0


def _atr_pct(c, i):
    return _ind(c, "atr14", lambda: atr(c))[i] / c["c"][i]


def _donch(c, i):
    return (_roll(c, "hi20", "h", 20, max)[i], _roll(c, "lo20", "l", 20, min)[i])


# ---------- signals ----------
def _break(c, i, d):
    hi, lo = _donch(c, i)
    return (d == 1 and c["c"][i] > hi) or (d == -1 and c["c"][i] < lo)


def breakout(c, btc, i, min_strength=0.0, need_slope=False):
    if i < warm(c) or not 0.01 <= _atr_pct(c, i) <= 0.06 or _vol_ratio(c, i) <= 1.5:
        return None
    d, strength, slope = _btc_trend(btc, i)
    if strength <= min_strength or (need_slope and not slope) or not _break(c, i, d):
        return None
    return "long" if d == 1 else "short"


def breakout_strong_btc(c, btc, i):
    return breakout(c, btc, i, min_strength=0.03, need_slope=True)


def pullback(c, btc, i):
    if i < warm(c):
        return None
    k = _k(c)
    e20, e50, slow = (_ind(c, ("ema", n), lambda n=n: _ema(c["c"], n)) for n in (20, 50, 300 * k))
    cl, o = c["c"][i], c["o"][i]
    if e20[i] > e50[i] and cl > slow[i] and c["l"][i] <= e20[i] < cl and cl > o:
        return "long"
    if e20[i] < e50[i] and cl < slow[i] and c["h"][i] >= e20[i] > cl and cl < o:
        return "short"
    return None


def squeeze(c, btc, i):
    if i < warm(c) or _vol_ratio(c, i) <= 1.5:
        return None
    bw = _bandwidth(c)
    if bw[i - 1] > min(bw[i - 120:i]) * 1.0001:      # bandwidth must sit at its 120-bar low just before the break
        return None
    hi, lo = _donch(c, i)
    return "long" if c["c"][i] > hi else "short" if c["c"][i] < lo else None


SIGNALS = {"breakout": breakout, "pullback": pullback, "breakout_strong_btc": breakout_strong_btc, "squeeze": squeeze}


# ---------- edge gate ----------
def best_signal(results: dict | None = None, tf: str | None = None) -> str | None:
    """Name of the signal passing EDGE_GATE overall and in both halves, highest avg R. results = backtest output."""
    if results is None:
        try:
            with open(RESULTS_FILE) as f:
                results = json.load(f)
        except (OSError, ValueError):
            return None
    g, best = EDGE_GATE, None
    for key, r in results.items():
        if tf and r.get("tf") != tf:
            continue
        if (r["trades"] >= g["min_trades"] and min(r["avg_r"], r["half1_avg_r"], r["half2_avg_r"]) >= g["min_avg_r"]
                and (best is None or r["avg_r"] > results[best]["avg_r"])):
            best = key
    return results[best].get("signal", best) if best else None


# ---------- universe + candles + scan ----------
def universe(ex, n: int = 10) -> list[str]:
    hit = _uni.get(n)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    markets = ex.load_markets()
    vol = {s: (t.get("quoteVolume") or 0) for s, t in ex.fetch_tickers().items()}
    ok = []
    for s, m in markets.items():
        info = m.get("info") or {}
        mn = ((m.get("limits") or {}).get("cost") or {}).get("min")
        if not (m.get("swap") and m.get("linear") and m.get("quote") == "USDT" and m.get("settle") == "USDT"
                and m.get("active") is not False and info.get("contractType", "PERPETUAL") == "PERPETUAL"):
            continue
        if m.get("base") in NON_CRYPTO | REGIME_ONLY or info.get("underlyingType", "COIN") != "COIN":
            continue
        if mn is None or mn > 5:
            continue
        ok.append(s)
    out = sorted(ok, key=lambda s: vol.get(s, 0), reverse=True)[:n]
    _uni[n] = (time.time(), out)
    return out


def to_candles(rows: list[list[float]]) -> dict:
    return {k: [r[j] for r in rows] for j, k in enumerate(("t", "o", "h", "l", "c", "v"))}


def candles(ex, symbol: str, tf: str = "4h", limit: int = 300) -> dict:
    return to_candles(ex.fetch_ohlcv(symbol, tf, limit=limit + 1)[:-1])    # drop the bar still forming


def scan(ex, symbols: list[str], signal: str | None = None, tf: str = "4h") -> list[dict]:
    signal = signal or best_signal(tf=tf)
    if not signal:
        return []
    fn = SIGNALS[signal]
    btc = candles(ex, "BTC/USDT:USDT", tf, 1000)
    out = []
    for s in symbols:
        try:
            c = candles(ex, s, tf, 1000)
            b = align(c, btc)
            i = len(c["c"]) - 1
            side = fn(c, b, i)
            if not side:
                continue
            a = _ind(c, "atr14", lambda: atr(c))[i]
            k = _k(c)
            e20, e50 = (_ind(c, ("ema", n), lambda n=n: _ema(c["c"], n))[i] for n in (20, 50))
            hi, lo = _donch(c, i)
            d, strength, _ = _btc_trend(b, i)
            out.append({"symbol": s, "side": side, "price": c["c"][i], "atr": a, "stop_dist": stop_mult(signal) * a,
                        "signal": signal, "bar_time": c["t"][i],
                        "features": {"rsi": round(rsi(c["c"][:i + 1]), 1), "ema_gap": e20 / e50 - 1,
                                     "atr_pct": a / c["c"][i], "vol_ratio": _vol_ratio(c, i), "donchian_hi": hi,
                                     "donchian_lo": lo, "btc_trend": d, "btc_strength": strength}})
        except Exception:
            continue
    return out


# ---------- derivatives store + crowding filter ----------
def _conn(db):
    return getattr(db, "db", db)


def store_derivs(ex, db, symbols: list[str]) -> None:
    db = _conn(db)
    db.execute("CREATE TABLE IF NOT EXISTS deriv (symbol TEXT, time INTEGER, funding REAL, oi REAL, ls REAL, taker REAL,"
               " PRIMARY KEY(symbol, time))")
    now = int(time.time()) // 900 * 900
    for s in symbols:
        try:
            mid = ex.market(s)["id"]
            prem = ex.fapiPublicGetPremiumIndex({"symbol": mid})
            oi = ex.fapiPublicGetOpenInterest({"symbol": mid})
            ls = ex.fapiDataGetGlobalLongShortAccountRatio({"symbol": mid, "period": "5m", "limit": 1})
            tk = ex.fapiDataGetTakerlongshortRatio({"symbol": mid, "period": "5m", "limit": 1})
            db.execute("INSERT OR REPLACE INTO deriv VALUES (?,?,?,?,?,?)",
                       (s, now, float(prem["lastFundingRate"]), float(oi["openInterest"]),
                        float(ls[-1]["longShortRatio"]), float(tk[-1]["buySellRatio"])))
        except Exception:
            continue


def derivs(db, symbol: str) -> dict:
    """Latest stored funding / long-short / taker ratio and the open-interest change over the last ~4 h."""
    try:
        rows = _conn(db).execute("SELECT time, funding, oi, ls, taker FROM deriv WHERE symbol = ? AND time >= "
                                 "(SELECT MAX(time) FROM deriv WHERE symbol = ?) - 4 * 3600 * 1000 ORDER BY time",
                                 (symbol, symbol)).fetchall()
    except Exception:
        return {}
    if not rows:
        return {}
    _, f, oi, ls, tk = rows[-1]
    oi0 = rows[0][2]
    chg = round((oi / oi0 - 1) * 100, 2) if oi and oi0 and len(rows) > 1 else None
    return {"funding": f, "oi": oi, "oi_change_pct_4h": chg, "ls": ls, "taker": tk}


def crowded(db, symbol: str, side: str) -> bool:
    try:
        row = _conn(db).execute("SELECT funding, ls FROM deriv WHERE symbol = ? ORDER BY time DESC LIMIT 1",
                                (symbol,)).fetchone()
    except Exception:
        return False
    if not row or row[0] is None or row[1] is None:
        return False
    f, ls = row
    return (side == "long" and f > 0.0003 and ls > 2.0) or (side == "short" and f < -0.0003 and ls < 0.5)
