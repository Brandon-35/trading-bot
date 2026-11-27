"""Backtest trade accounting on crafted series (exact R incl. fees) and the stats table. No network."""
import pytest

from trader import backtest as bt
from trader import signals as sg
from trader.signals import warm

H4 = 14_400_000
TK, MK = bt.TAKER, bt.MAKER


def flat(n=320):
    c = {"t": [1_700_000_000_000 + i * H4 for i in range(n)], "o": [100.0] * n, "h": [101.0] * n,
         "l": [99.0] * n, "c": [100.0] * n, "v": [100.0] * n}
    return c


@pytest.fixture
def fire(monkeypatch):
    monkeypatch.setitem(sg.SIGNALS, "once", lambda c, b, i: "long" if i == warm(c) else None)
    monkeypatch.setitem(sg.STOP_MULT, "once", 2.0)


def bar(c, j, h, l, close=100.0):
    c["h"][j], c["l"][j], c["c"][j], c["o"][j] = h, l, close, 100.0


def test_stop_out_exact(fire):
    c = flat()
    w = warm(c)
    bar(c, w + 1, 100.5, 95.0)                       # atr=2 -> dist 4, stop 96
    (t,) = bt.simulate(c, c, "once")
    assert t["r"] == pytest.approx(-1 - TK * 100 / 4 - TK * 96 / 4)


def test_tp1_then_trail_exact(fire):
    c = flat()
    w = warm(c)
    bar(c, w + 1, 108.5, 99.5)                       # tp1 at 108; ext 108.5; tr=9 -> atr=(13*2+9)/14=2.5; trail 102.25
    bar(c, w + 2, 101.0, 99.0)                       # low under the trail -> exit at 102.25
    (t,) = bt.simulate(c, c, "once")
    exp = (-TK * 100 / 4) + (1 - 0.5 * MK * 108 / 4) + (0.5 * (102.25 - 100) / 4 - 0.5 * TK * 102.25 / 4)
    assert t["r"] == pytest.approx(exp)


def test_open_trade_closed_at_last_close(fire):
    c = flat()
    (t,) = bt.simulate(c, c, "once")
    assert t["r"] == pytest.approx(-2 * TK * 100 / 4)


def test_stats_and_halves():
    mk = lambda tin, tout, r: {"symbol": "X", "side": "long", "t_in": tin, "t_out": tout, "r": r}
    ts = [mk(0, 1, 1.0), mk(2, 3, -1.0), mk(4, 5, -1.0), mk(10, 11, 3.0), mk(12, 13, 1.0)]
    s = bt.stats(ts, 10)
    assert s["trades"] == 5 and s["trades_per_day"] == 0.5
    assert s["avg_r"] == pytest.approx(0.6) and s["median_r"] == 1.0
    assert s["win_rate"] == pytest.approx(0.6) and s["max_consec_losses"] == 2
    assert s["max_dd_r"] == pytest.approx(2.0)       # equity 1,0,-1,2,3 -> drawdown 2 from the peak of 1
    assert s["half1_trades"] == 3 and s["half1_avg_r"] == pytest.approx(-1 / 3)
    assert s["half2_trades"] == 2 and s["half2_avg_r"] == pytest.approx(2.0)


def test_run_returns_dict(fire):
    c = flat()
    bar(c, warm(c) + 1, 100.5, 95.0)
    res = bt.run({"X/USDT:USDT": c}, c, ["once"], "4h", 10)
    r = res["once:4h"]
    assert r["trades"] == 1 and r["avg_r"] < -1 and r["signal"] == "once" and "once:4h" in bt.table(res)
