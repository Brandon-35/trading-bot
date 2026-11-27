"""Signals, universe filter and crowding filter on synthetic data (no network)."""
import sqlite3
import time

import pytest

from trader import signals as sg

H4 = 14_400_000


def mk(closes, vol=None, spread=0.8, t0=1_700_000_000_000):
    n = len(closes)
    return {"t": [t0 + i * H4 for i in range(n)], "o": list(closes), "h": [x + spread for x in closes],
            "l": [x - spread for x in closes], "c": list(closes), "v": vol or [100.0] * n}


def uptrend(n=400):
    return [100 + 0.05 * i + (0.3 if i % 2 else -0.3) for i in range(n)]


def test_atr_known_series():
    c = mk([10.0] * 20, spread=1.0)
    assert sg.atr(c, 14)[-1] == pytest.approx(2.0)
    c = mk([10 + i for i in range(20)], spread=0.5)          # tr = max(1, |h-pc|=1.5, |l-pc|=0.5) = 1.5
    assert sg.atr(c, 14)[-1] == pytest.approx(1.5)


def test_breakout_fires_on_crafted_break_not_noise():
    cl = uptrend()
    btc = mk(cl)
    c = mk(cl)
    i = len(cl) - 1
    assert sg.breakout(c, btc, i) is None                    # noise: no volume, no new high
    c["c"][i] = max(c["h"][i - 20:i]) + 1.5                  # clean break, 1.5% of price
    c["h"][i] = c["c"][i] + 0.3
    c["v"][i] = 300
    c.pop("_x")
    assert sg.breakout(c, btc, i) == "long"
    c["v"][i] = 100
    c.pop("_x")
    assert sg.breakout(c, btc, i) is None                    # no volume confirmation


def test_breakout_needs_btc_direction():
    cl = uptrend()
    c = mk(cl)
    i = len(cl) - 1
    c["c"][i] = max(c["h"][i - 20:i]) + 1.5
    c["v"][i] = 300
    down = mk([300 - 0.05 * j for j in range(len(cl))])
    assert sg.breakout(c, down, i) is None                   # long break against a BTC downtrend


class FakeEx:
    def __init__(self, markets, vols):
        self._m, self._v = markets, vols

    def load_markets(self):
        return self._m

    def fetch_tickers(self):
        return {s: {"quoteVolume": v} for s, v in self._v.items()}


def mkt(base, mn=5, **kw):
    m = {"swap": True, "linear": True, "quote": "USDT", "settle": "USDT", "active": True, "base": base,
         "limits": {"cost": {"min": mn}}, "info": {"contractType": "PERPETUAL", "underlyingType": "COIN"}}
    return m | kw


def test_universe_filters():
    sym = lambda b: f"{b}/USDT:USDT"
    markets = {sym("BTC"): mkt("BTC", 50), sym("ETH"): mkt("ETH", 20), sym("SOL"): mkt("SOL"), sym("XRP"): mkt("XRP"),
               sym("NVDA"): mkt("NVDA"), sym("XAU"): mkt("XAU"), sym("ODD"): mkt("ODD", 5, info={"underlyingType": "TRADFI"}),
               sym("BIG"): mkt("BIG", 20), sym("OFF"): mkt("OFF", active=False), sym("DOGE"): mkt("DOGE"),
               "SOL/USDT": mkt("SOL", swap=False)}
    vols = {sym(b): v for b, v in dict(BTC=9, ETH=8, SOL=5, XRP=7, NVDA=99, XAU=98, ODD=97, BIG=96, OFF=95, DOGE=6).items()}
    sg._uni.clear()
    assert sg.universe(FakeEx(markets, vols), 10) == [sym("XRP"), sym("DOGE"), sym("SOL")]
    sg._uni.clear()
    assert sg.universe(FakeEx(markets, vols), 2) == [sym("XRP"), sym("DOGE")]
    ex2 = FakeEx({}, {})
    assert sg.universe(ex2, 2) == [sym("XRP"), sym("DOGE")]  # served from the 24 h cache
    sg._uni.clear()


def test_crowded():
    db = sqlite3.connect(":memory:")
    assert sg.crowded(db, "SOL", "long") is False            # no table
    db.execute("CREATE TABLE deriv (symbol TEXT, time INTEGER, funding REAL, oi REAL, ls REAL, taker REAL,"
               " PRIMARY KEY(symbol,time))")
    assert sg.crowded(db, "SOL", "long") is False            # no row
    db.execute("INSERT INTO deriv VALUES ('SOL', 1, 0.0005, 1, 2.5, 1)")
    db.execute("INSERT INTO deriv VALUES ('ADA', 1, -0.0005, 1, 0.4, 1)")
    db.execute("INSERT INTO deriv VALUES ('XRP', 1, 0.0005, 1, 1.0, 1)")
    assert sg.crowded(db, "SOL", "long") and not sg.crowded(db, "SOL", "short")
    assert sg.crowded(db, "ADA", "short") and not sg.crowded(db, "ADA", "long")
    assert not sg.crowded(db, "XRP", "long")
    db.execute("INSERT INTO deriv VALUES ('SOL', 2, 0.0001, 1, 2.5, 1)")   # latest row wins
    assert not sg.crowded(db, "SOL", "long")


def test_best_signal_gate():
    ok = {"trades": 200, "avg_r": 0.2, "half1_avg_r": 0.15, "half2_avg_r": 0.25, "tf": "4h"}
    res = {"a:4h": ok | {"signal": "a"}, "b:4h": ok | {"avg_r": 0.3, "signal": "b"},
           "c:4h": ok | {"half1_avg_r": -0.1, "avg_r": 0.9, "signal": "c"}, "d:4h": ok | {"trades": 100, "signal": "d"}}
    assert sg.best_signal(res) == "b"
    assert sg.best_signal({"c:4h": res["c:4h"], "d:4h": res["d:4h"]}) is None


def test_store_derivs_writes_row():
    class Ex:
        def market(self, s):
            return {"id": "SOLUSDT"}
        fapiPublicGetPremiumIndex = lambda self, p: {"lastFundingRate": "0.0001"}
        fapiPublicGetOpenInterest = lambda self, p: {"openInterest": "1000"}
        fapiDataGetGlobalLongShortAccountRatio = lambda self, p: [{"longShortRatio": "1.5"}]
        fapiDataGetTakerlongshortRatio = lambda self, p: [{"buySellRatio": "0.9"}]
    db = sqlite3.connect(":memory:")
    sg.store_derivs(Ex(), db, ["SOL/USDT:USDT"])
    sym, f, oi, ls, tk, t = db.execute("SELECT symbol, funding, oi, ls, taker, time FROM deriv").fetchone()
    assert (sym, f, oi, ls, tk) == ("SOL/USDT:USDT", 0.0001, 1000.0, 1.5, 0.9)
    assert abs(t - time.time()) < 900
