"""Broker failure paths with fake ccxt objects (no network)."""
import time

import pytest

from trader import main as m
from trader.exchange import Binance, Paper
from trader.risk import Limits
from trader.store import Store

S = "SOL/USDT:USDT"


class FakeCcxt:
    def __init__(self, fail_on=None):
        self.orders, self.fail_on, self.pos = [], fail_on, {}

    def create_order(self, sym, typ, side, qty, price=None, params=None):
        params = params or {}
        kind = "sl" if "stopLossPrice" in params else "tp" if "takeProfitPrice" in params else \
            "exit" if params.get("reduceOnly") else "entry"
        self.orders.append(kind)
        if kind == self.fail_on:
            raise RuntimeError(f"{kind} rejected")
        if kind == "entry":
            self.pos[sym] = qty
        if kind == "exit":
            if sym not in self.pos:
                raise RuntimeError("-2022 ReduceOnly Order is rejected")
            self.pos.pop(sym)
        return {"id": len(self.orders)}

    def price_to_precision(self, s, p): return str(p)
    def fetch_positions(self): return [{"symbol": s, "contracts": q, "side": "long", "entryPrice": 70} for s, q in self.pos.items()]
    def fetch_open_orders(self, s, params=None): return []
    def cancel_all_orders(self, s, params=None): pass


def broker(fake):
    b = Binance.__new__(Binance)      # skip __init__: no markets / leverage calls
    b.ex = b.data = fake
    return b


def test_sl_failure_flattens_and_raises():
    fake = FakeCcxt(fail_on="sl")
    with pytest.raises(RuntimeError):
        broker(fake).open(S, "long", 1.0, 69, 73)
    assert fake.orders == ["entry", "sl", "exit"] and S not in fake.pos


def test_ambiguous_entry_failure_is_safe_when_nothing_filled():
    fake = FakeCcxt(fail_on="entry")
    with pytest.raises(RuntimeError):
        broker(fake).open(S, "long", 1.0, 69, 73)
    assert fake.orders == ["entry", "exit"] and not fake.pos   # exit rejected as already flat, no retry loop


def test_close_exits_before_cancelling():
    fake = FakeCcxt()
    fake.pos[S] = 1.0
    calls = []
    fake.cancel_order = lambda i, s, params=None: calls.append("cancel")
    fake.fetch_open_orders = lambda s, params=None: [{"id": 1, "clientOrderId": "x-cvBPrNm9z"}]
    orig = fake.create_order
    fake.create_order = lambda *a, **k: (calls.append("exit"), orig(*a, **k))[1]
    broker(fake).close(S)
    assert calls == ["exit", "cancel"]


def test_cancel_protective_leaves_hand_orders_alone():
    fake = FakeCcxt()
    cancelled = []
    fake.fetch_open_orders = lambda s, params=None: [{"id": 1, "clientOrderId": "x-cvBPrNm9a"},
                                                      {"id": 2, "clientOrderId": "web_hand"}, {"id": 3, "info": {}}]
    fake.cancel_order = lambda i, s, params=None: cancelled.append((i, params))
    b = broker(fake)
    assert b.protective_count(S) == 1
    b.cancel_protective(S)
    assert cancelled == [(1, {"trigger": True})]


class FakeData:
    def __init__(self, candles, last=70.0):
        self.candles, self.last = candles, last
    def load_markets(self): pass
    def fetch_ticker(self, s): return {"last": self.last}
    def fetch_ohlcv(self, s, tf, since=None, limit=None): return [c for c in self.candles if c[0] >= since]
    def fetch_funding_rate(self, s): return {"fundingRate": 0.0}


def test_paper_stop_fills_at_gap_open_and_state_survives_restart(tmp_path):
    st = Store(str(tmp_path / "p.db"))
    save = lambda s: st.log("paper_state", **s)
    future = int(time.time() * 1000) + 120_000
    data = FakeData([[future, 68.0, 68.5, 67.5, 68.0, 1]])      # gaps below the 69 stop
    p = Paper(data, 5, 100.0, save=save)
    p.open(S, "long", 1.0, 69.0, 73.0)
    p2 = Paper(data, 5, 100.0, state=st.last("paper_state"), save=save)   # "restart"
    assert S in p2.positions()
    closed = []
    p2.on_close = lambda **t: closed.append(t)
    p2.tick()
    assert closed and closed[0]["why"] == "stop_loss" and closed[0]["exit"] < 68.0   # filled at open 68 minus slippage
    assert Paper(data, 5, 100.0, state=st.last("paper_state")).positions() == {}


def test_day_start_uses_equity_from_before_midnight(tmp_path):
    st = Store(str(tmp_path / "d.db"))
    st.log("day_start", date="2000-01-01", equity=100)
    st.log("equity", equity=95)                       # last value seen yesterday
    bot = m.Bot(None, None, st, Limits(), "paper")
    assert bot.day_start_equity(90) == 95


def test_limits_refuse_values_above_plan():
    with pytest.raises(ValueError):
        Limits(risk_pct=0.05)
    with pytest.raises(ValueError):
        Limits(leverage=10)
