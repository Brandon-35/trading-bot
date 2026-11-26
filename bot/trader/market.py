"""Market data and indicators. The LLM gets numbers computed here, never raw math to do."""


def ema(values: list[float], n: int) -> float:
    k = 2 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes: list[float], n: int = 14) -> float:
    gains = losses = 0.0
    for a, b in zip(closes[-n - 1:-1], closes[-n:]):
        d = b - a
        gains += max(d, 0)
        losses += max(-d, 0)
    return 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)


def atr(candles: list[list[float]], n: int = 14) -> float:
    """candles: [ts, o, h, l, c, v]; simple average of the true range over n bars."""
    trs = [max(c[2] - c[3], abs(c[2] - p[4]), abs(c[3] - p[4])) for p, c in zip(candles[-n - 1:-1], candles[-n:])]
    return sum(trs) / len(trs)


def snapshot(ex, symbols: list[str]) -> tuple[dict, dict]:
    """Return (snapshot for the LLM, {symbol: {price, atr}} for the risk checks)."""
    out, ref = {}, {}
    for s in symbols:
        h1 = ex.fetch_ohlcv(s, "1h", limit=100)[:-1]     # drop the candle still forming
        h4 = ex.fetch_ohlcv(s, "4h", limit=51)[:-1]
        m15 = ex.fetch_ohlcv(s, "15m", limit=51)[:-1]
        price = float(ex.fetch_ticker(s)["last"])
        closes = [c[4] for c in h1]
        a = atr(h1)
        try:
            funding = ex.fetch_funding_rate(s).get("fundingRate")
        except Exception:
            funding = None
        out[s] = {"price": price, "atr_1h": round(a, 6), "rsi_1h": round(rsi(closes), 1),
                  "ema20_1h": round(ema(closes, 20), 6), "ema50_1h": round(ema(closes, 50), 6), "funding": funding,
                  "candles_4h": [c[1:] for c in h4], "candles_1h": [c[1:] for c in h1[-50:]],
                  "candles_15m": [c[1:] for c in m15]}
        ref[s] = {"price": price, "atr": a}
    return out, ref
