"""v2 entries, stop replacement, trailing, reconcile and paper accounting against fakes (no network)."""
import os
import time

os.environ.setdefault("LLM_MODEL", "x")
os.environ.setdefault("LLM_BASE_URL", "http://localhost")
os.environ.setdefault("LLM_API_KEY", "x")

import pytest

from trader import main as m
from trader.exchange import Binance, Paper
from trader.risk import V2Limits
from trader.store import Store

S = "SOL/USDT:USDT"
MKT = {"precision": {"amount": 0.1}, "limits": {"amount": {"min": 0.1}, "cost": {"min": 5}}}
CID = "x-cvBPrNm9a"


# ---- Binance.open_v2 / move_stop with a fake ccxt -----------------------------------------------------------------

class FakeX:
    def __init__(self, fill=0.0, last=100.0, bid=100.0, fail=None):
        self.fill, self.last, self.bid, self.fail = fill, last, bid, fail
        self.log, self.triggers, self.market_qty, self.limit_qty, self.canceled, self.n = [], [], 0.0, 0.0, False, 0

    def set_margin_mode(self, *a): self.log.append(("margin",) + a)
    def set_leverage(self, *a): self.log.append(("leverage",) + a)
    def market(self, s): return MKT
    def price_to_precision(self, s, p): return str(p)
    def fetch_ticker(self, s): return {"bid": self.bid, "ask": self.bid + 0.1, "last": self.last}

    def maker(self): return round(self.limit_qty * self.fill, 6)

    def fetch_order(self, oid, s):
        return {"filled": self.maker(), "status": "canceled" if self.canceled else "open"}

    def cancel_order(self, oid, s, params=None):
        self.log.append(("cancel", oid))
        if params and params.get("trigger"):
            self.triggers = [t for t in self.triggers if t["id"] != oid]
        else:
            self.canceled = True

    def create_order(self, s, typ, side, qty, price=None, params=None):
        params = params or {}
        self.n += 1
        key = "stop" if "stopLossPrice" in params else "tp" if "takeProfitPrice" in params else \
            "exit" if params.get("reduceOnly") else typ
        self.log.append((key, side, qty, price, params))
        if key == self.fail:
            raise RuntimeError(f"{key} rejected")
        if typ == "limit":
            assert params == {"timeInForce": "GTX"}
            self.limit_qty = qty
            return {"id": "L1"}
        if key in ("stop", "tp"):
            self.triggers.append({"id": f"T{self.n}", "clientOrderId": CID, "amount": qty,
                                  "info": {"origType": "STOP_MARKET" if key == "stop" else "TAKE_PROFIT_MARKET"}})
            return {"id": f"T{self.n}"}
        if key == "exit":
            self.market_qty = self.limit_qty = 0.0
            return {"id": f"X{self.n}"}
        self.market_qty += qty
        return {"id": f"M{self.n}"}

    def fetch_positions(self):
        q = self.maker() + self.market_qty
        return [{"symbol": S, "contracts": q, "side": "long", "entryPrice": 100.0}] if q > 0 else []

    def fetch_open_orders(self, s, params=None): return list(self.triggers)


def binance(fake):
    b = Binance.__new__(Binance)
    b.ex = b.data = fake
    b.after_order = lambda s: None
    b._sleep = lambda s: None
    b.entry_wait = 4.0
    return b


def kinds(fake): return [e[0] for e in fake.log]


def test_maker_fill_places_stop_for_full_qty_and_tp_for_half():
    f = FakeX(fill=1.0)
    r = binance(f).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    assert r == {"qty": 1.0, "entry": 100.0, "tp_qty": 0.5, "maker": True}
    assert "market" not in kinds(f)
    lim = next(e for e in f.log if e[0] == "limit")
    assert lim[3] == 100.0 and lim[4] == {"timeInForce": "GTX"}          # best bid, post-only
    stop = next(e for e in f.log if e[0] == "stop")
    tp = next(e for e in f.log if e[0] == "tp")
    assert stop[2] == 1.0 and stop[4]["reduceOnly"] and stop[4]["workingType"] == "MARK_PRICE" and stop[1] == "sell"
    assert tp[2] == 0.5 and tp[4]["reduceOnly"]
    assert ("leverage", 3, S) in f.log and ("margin", "isolated", S) in f.log


def test_unfilled_entry_falls_back_to_market_while_the_setup_holds():
    f = FakeX(fill=0.0, last=100.4)                                       # within 0.5 ATR (1.25) of 100
    r = binance(f).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    assert r["qty"] == 1.0 and r["maker"] is False
    assert kinds(f).index("cancel") < kinds(f).index("market") < kinds(f).index("stop")


def test_unfilled_entry_is_dropped_when_the_price_ran_away():
    f = FakeX(fill=0.0, last=101.5)                                       # 1.5 > 1.25
    assert binance(f).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3) is None
    assert "market" not in kinds(f) and "stop" not in kinds(f) and f.canceled


def test_partial_fill_uses_the_filled_qty_and_markets_only_the_rest():
    f = FakeX(fill=0.4)
    r = binance(f).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    mk = next(e for e in f.log if e[0] == "market")
    assert mk[2] == pytest.approx(0.6) and r["qty"] == pytest.approx(1.0)
    f2 = FakeX(fill=0.4, last=105.0)                                      # ran away: keep only the 0.4
    r = binance(f2).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    assert r["qty"] == pytest.approx(0.4) and "market" not in kinds(f2)
    assert next(e for e in f2.log if e[0] == "stop")[2] == pytest.approx(0.4)


def test_failed_protection_flattens_and_raises():
    f = FakeX(fill=1.0, fail="stop")
    with pytest.raises(RuntimeError):
        binance(f).open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    assert "exit" in kinds(f) and f.fetch_positions() == []


def test_stop_replacement_places_the_new_stop_before_cancelling_the_old():
    f = FakeX(fill=1.0)
    b = binance(f)
    b.open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    old = next(t["id"] for t in f.triggers if t["info"]["origType"] == "STOP_MARKET")
    f.log.clear()
    b.move_stop(S, 100.0, 0.5)
    assert kinds(f) == ["stop", "cancel"] and f.log[1] == ("cancel", old)
    stops = [t for t in f.triggers if t["info"]["origType"] == "STOP_MARKET"]
    assert len(stops) == 1 and stops[0]["amount"] == 0.5 and b.stop_cover(S) == 0.5


def test_failed_new_stop_leaves_the_old_one_in_place():
    f = FakeX(fill=1.0)
    b = binance(f)
    b.open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    f.fail = "stop"
    with pytest.raises(RuntimeError):
        b.move_stop(S, 100.0, 1.0)
    assert b.stop_cover(S) == 1.0


def test_stop_cover_ignores_take_profits_and_hand_orders():
    f = FakeX(fill=1.0)
    b = binance(f)
    b.open_v2(S, "long", 1.0, 95, 110, 100.0, 2.5, 3)
    f.triggers.append({"id": "H", "clientOrderId": "web_hand", "amount": 9, "info": {"origType": "STOP_MARKET"}})
    assert b.stop_cover(S) == 1.0


# ---- Paper ------------------------------------------------------------------------------------------------------

class FakeData:
    def __init__(self, candles=(), last=100.0, bid=100.0):
        self.candles, self.last, self.bid = list(candles), last, bid
    def load_markets(self): pass
    def market(self, s): return MKT
    def fetch_ticker(self, s): return {"last": self.last, "bid": self.bid, "ask": self.bid + 0.1}
    def fetch_ohlcv(self, s, tf, since=None, limit=None): return [c for c in self.candles if c[0] >= since]
    def fetch_funding_rate(self, s): return {"fundingRate": 0.01}


def paper(data, closed=None, **kw):
    p = Paper(data, 1, 100.0, on_close=lambda **t: closed.append(t) if closed is not None else None, funding=False, **kw)
    p._sleep = lambda s: setattr(data, "last", data.bid)     # the price touches our bid on the first poll
    p.entry_wait = 4.0
    return p


def test_paper_post_only_fills_as_maker_and_falls_back_to_taker():
    d = FakeData()
    p = paper(d)
    r = p.open_v2(S, "long", 10.0, 98, 104, 100.0, 2.5, 2)
    assert r["maker"] and r["entry"] == 100.0 and r["tp_qty"] == 5.0
    assert p.cash == pytest.approx(100 - 100 * 10 * 0.0002)             # maker fee, no slippage
    d2 = FakeData(last=100.5)
    p2 = paper(d2)
    p2._sleep = lambda s: setattr(d2, "last", 100.5)                      # never touches the bid
    r = p2.open_v2(S, "long", 10.0, 98, 104, 100.0, 2.5, 2)
    assert not r["maker"] and r["entry"] == pytest.approx(100.5 * 1.0002)
    assert p2.cash == pytest.approx(100 - r["entry"] * 10 * 0.0005)     # taker fee + slippage
    d3 = FakeData(last=102.0)
    p3 = paper(d3)
    p3._sleep = lambda s: setattr(d3, "last", 102.0)
    assert p3.open_v2(S, "long", 10.0, 98, 104, 100.0, 2.5, 2) is None  # 2.0 > 0.5 ATR: no trade
    assert p3.positions() == {}


def test_paper_partial_tp_then_moved_stop_gives_net_r_with_fees():
    now = int(time.time() * 1000)
    t0 = now // 60_000 * 60_000 - 600_000
    d = FakeData([[t0, 100, 104.5, 100.5, 104, 1]])                    # settled candle: TP (104) hit, stop (98) not
    closed = []
    p = paper(d, closed)
    p.open_v2(S, "long", 10.0, 98, 104, 100.0, 2.5, 2)
    p.pos[S]["opened"] = t0 - 60_000
    p.tick()
    assert p.positions()[S]["qty"] == 5.0 and not closed                # half closed, position stays
    p.move_stop(S, 100.0, 5.0)                                          # breakeven
    p.tick()                                                            # old candle must not hit the new stop
    assert S in p.pos
    d.candles.append([t0 + 60_000, 101, 102, 99, 99.5, 1])               # falls through 100
    p.tick()
    assert not p.pos and len(closed) == 1
    c = closed[0]
    tp_px, sl_px = 104 * 0.9998, 100 * 0.9998
    fees = 100 * 10 * 0.0002 + tp_px * 5 * 0.0005 + sl_px * 5 * 0.0005
    net = (tp_px - 100) * 5 + (sl_px - 100) * 5 - fees
    assert c["why"] == "stop_loss" and c["qty"] == 10.0 and c["pnl"] == pytest.approx(net)
    assert c["fees"] == pytest.approx(fees) and c["r"] == pytest.approx(net / (10 * 2))   # risk0 = 10 * |100-98|
    assert p.cash == pytest.approx(100 + net)
    assert c["exit"] == pytest.approx((tp_px + sl_px) / 2)


def test_paper_v1_open_still_exits_everything_at_tp():
    now = int(time.time() * 1000)
    t0 = now // 60_000 * 60_000 - 600_000
    d = FakeData([[t0, 100, 111, 99.5, 110, 1]])
    closed = []
    p = paper(d, closed)
    p.open(S, "long", 2.0, 95, 110)
    p.pos[S]["opened"] = t0 - 60_000
    p.tick()
    assert not p.pos and closed[0]["why"] == "take_profit" and closed[0]["qty"] == 2.0 and closed[0]["r"] > 0


def test_paper_old_saved_state_without_v2_fields_still_loads():
    st = {"cash": 90.0, "pos": {S: {"side": "long", "qty": 1.0, "entry": 100.0, "sl": 95.0, "tp": 110.0,
                                    "fees": 0.05, "funding": 0.0, "opened": 1}}, "last_funding_hour": None}
    p = Paper(FakeData(), 5, state=st)
    assert p.pos[S]["tp_qty"] == 1.0 and p.pos[S]["qty0"] == 1.0 and p.stop_cover(S) == 1.0


# ---- BotV2 ------------------------------------------------------------------------------------------------------

class Sig:
    def __init__(self, setups=(), crowd=False):
        self.setups, self.crowd = list(setups), crowd
    def universe(self, ex, n=10): return [S]
    def store_derivs(self, ex, db, syms): pass
    def best_signal(self): return None
    def crowded(self, db, s, side): return self.crowd
    def scan(self, ex, syms, signal, tf): return self.setups


class FB:
    """Fake broker for BotV2."""
    def __init__(self, positions=None, cover=None, equity=100.0, free=100.0, last=100.0):
        self.pos, self.cover, self._eq, self.free, self.calls = positions or {}, cover, equity, free, []
        self.data = FakeData(last=last)
    def positions(self): return {k: dict(v) for k, v in self.pos.items()}
    def equity(self): return self._eq
    def free_margin(self): return self.free
    def market(self, s): return MKT
    def stop_cover(self, s): return self.pos[s]["qty"] if self.cover is None else self.cover
    def protective_count(self, s): return 1
    def cancel_protective(self, s): self.calls.append(("cancel", s))
    def close(self, s): self.calls.append(("close", s)); self.pos.pop(s, None)
    def move_stop(self, s, new, qty): self.calls.append(("move_stop", s, new, qty))
    def open_v2(self, s, side, qty, sl, tp, setup_price, atr, lev, tp_frac=0.5):
        self.calls.append(("open_v2", s, side, qty, sl, tp, lev))
        self.pos[s] = {"side": side, "qty": qty, "entry": setup_price}
        return {"qty": qty, "entry": setup_price, "tp_qty": round(qty / 2, 6), "maker": True}


def bot2(broker, tmp_path, sig=None, mode="paper", arm="signal", **kw):
    return m.BotV2(broker, Store(str(tmp_path / "v2.db")), V2Limits(), mode, arm, sig or Sig(), **kw)


def setup(side="long", price=100.0, atr=2.5, bar=1):
    return {"symbol": S, "side": side, "price": price, "atr": atr, "stop_dist": 2 * atr, "signal": "breakout",
            "bar_time": bar, "features": {}}


def pos_state(side="long", entry=100.0, stop=95.0, qty0=1.0, **k):
    return {"side": side, "qty0": qty0, "entry": entry, "stop": stop, "stop0": stop, "tp": 110.0, "tp_qty": qty0 / 2,
            "atr": 2.5, "dist0": abs(entry - stop), "tp1_done": False, "extreme": entry, "opened": 0, "lev": 3} | k


def test_entry_is_sized_from_base_with_two_percent_risk_and_sl_2atr_tp_2r(tmp_path):
    b = FB(equity=100.0)
    x = bot2(b, tmp_path)
    x.enter(setup(), x.base())
    # risk 2.00 / stop 5.0 = 0.4 SOL, notional 40 <= margin -> 1x; SL 95, TP1 110 (2R)
    assert b.calls == [("open_v2", S, "long", 0.4, 95.0, 110.0, 1)]
    st = x.state[S]
    assert st["stop"] == 95.0 and st["tp_qty"] == 0.2 and st["lev"] == 1 and not st["tp1_done"]
    assert x.store.last("trade_open")["risk_pct"] == 0.02
    assert x.store.last("decision")["accepted"] is True


def fresh(tmp_path, name, **fb):
    (tmp_path / name).mkdir()
    b = FB(**fb)
    return b, bot2(b, tmp_path / name)


@pytest.mark.parametrize("price, atr, qty", [
    (10.0, 0.3, 0.6),      # risk 18.7392 * 2 % = 0.3748 / stop 0.6
    (5.0, 0.1, 1.8),       # 0.3748 / 0.2
    (100.0, 1.0, 0.1),     # 0.3748 / 2 = 0.187 -> 0.1 SOL = 10 USDT
])
def test_entry_is_sized_from_base_not_wallet(tmp_path, price, atr, qty):
    b, x = fresh(tmp_path, "a", equity=18.7392, free=1000.0)    # a huge wallet changes nothing
    x.enter(setup(price=price, atr=atr), x.base())
    assert b.calls and b.calls[0][3] == qty


def test_entry_below_min_qty_is_rejected_not_rounded_up(tmp_path):
    b, x = fresh(tmp_path, "a", equity=18.7392)
    x.enter(setup(price=100.0, atr=1.9), x.base())      # 0.3748 / 3.8 = 0.098 -> rounds down to 0 < min qty 0.1
    assert not b.calls and x.store.last("decision")["reject"].startswith("qty")


def test_entry_below_min_notional_is_rejected(tmp_path):
    b, x = fresh(tmp_path, "a", equity=18.7392)
    x.enter(setup(price=1.0, atr=0.1), x.base())       # 0.3748 / 0.2 = 1.8 SOL * 1 = 1.8 USDT < 5
    assert not b.calls and "min notional" in x.store.last("decision")["reject"]


def test_same_bar_is_acted_on_once_and_rejections_are_logged(tmp_path):
    b = FB()
    x = bot2(b, tmp_path, Sig(crowd=True))
    x.enter(setup(bar=7), 100.0)
    x.enter(setup(bar=7), 100.0)
    assert not b.calls and len(x.store.all("setup")) == 1
    assert x.store.last("decision")["reject"] == "crowded"


def test_symbol_with_any_position_is_skipped(tmp_path):
    b = FB({S: {"side": "long", "qty": 1.0, "entry": 100.0}})
    x = bot2(b, tmp_path)
    x.enter(setup(), 100.0)
    assert not b.calls and "already open" in x.store.last("decision")["reject"]


def test_caps_block_a_third_same_side_and_total_risk(tmp_path):
    b = FB({"A": {"side": "long", "qty": 1.0, "entry": 100.0}, "B": {"side": "long", "qty": 1.0, "entry": 100.0}})
    x = bot2(b, tmp_path)
    x.state = {"A": pos_state(), "B": pos_state()}
    x.enter(setup(), 100.0)
    assert not b.calls and "long" in x.store.last("decision")["reject"]
    x.enter(setup("short", bar=2), 100.0)                       # new risk 2.0 + 5 + 5 = 12 > 10 % of 100
    assert not b.calls and "total open risk" in x.store.last("decision")["reject"]


def test_daily_entry_cap(tmp_path):
    x = bot2(FB(), tmp_path)
    for _ in range(6):
        x.store.log("trade_open", symbol="X")
    x.enter(setup(), 100.0)
    assert "entries" in x.store.last("decision")["reject"]


def test_leverage_comes_from_free_margin_and_liquidation_rejects(tmp_path):
    b = FB(equity=100.0, free=10.0)
    x = bot2(b, tmp_path)
    x.enter(setup(), 100.0)                                      # notional 40, 10 margin -> 5x
    assert b.calls[0][-1] == 5
    b2 = FB(equity=100.0, free=3.0)
    y = bot2(b2, tmp_path)
    y.enter(setup(bar=9), 100.0)                                 # needs 14x > 10x
    assert not b2.calls and "more than 10x" in y.store.last("decision")["reject"]


def test_committee_arm_uses_the_leads_numbers_and_skip_is_default(tmp_path):
    class C:
        def __init__(self, res): self.res = res
        def decide(self, setup, ctx, recent, store): return self.res
    b = FB()
    x = bot2(b, tmp_path, arm="committee", committee=C({"action": "skip", "side": "long"}))
    x.enter(setup(bar=1), 100.0)
    assert not b.calls
    x.committee = C({"action": "open", "side": "long", "confidence": 0.7, "sl_atr": 1.5, "tp_r": 3, "rationale": "r"})
    x.enter(setup(bar=2), 100.0)                                 # stop 3.75: SL 96.25, TP 100 + 3*3.75
    assert b.calls[0][4:6] == (96.25, 111.25)
    b.pos.clear()                                                 # the long above is closed again
    x.committee = C({"action": "open", "side": "short", "sl_atr": 1.5, "tp_r": 3})
    x.enter(setup(bar=3), 100.0)
    assert "side" in x.store.last("decision")["reject"]
    x.state.clear()
    x.committee = C({"action": "open", "side": "long", "sl_atr": 9, "tp_r": 3})
    x.enter(setup(bar=4), 100.0)
    assert "out of range" in x.store.last("decision")["reject"]


def test_halved_risk_after_two_losing_trades(tmp_path):
    b = FB()
    x = bot2(b, tmp_path)
    x.store.log("trade_close", symbol="X", r=-1.0)
    x.store.log("trade_close", symbol="X", r=-1.0)
    x.enter(setup(), 100.0)
    assert b.calls[0][3] == 0.2 and x.store.last("trade_open")["risk_pct"] == 0.01


# ---- reconcile ----------------------------------------------------------------------------------------------------

def test_reconcile_keeps_a_position_whose_stop_covers_it_and_closes_one_without(tmp_path):
    pos = {S: {"side": "long", "qty": 1.0, "entry": 100.0}}
    b = FB(dict(pos), cover=1.0)
    x = bot2(b, tmp_path)
    x.reconcile(b.positions())
    assert not b.calls
    b2 = FB(dict(pos), cover=0.0)
    y = bot2(b2, tmp_path)
    y.reconcile(b2.positions())
    assert b2.calls == [("close", S)] and y.store.last("reconcile_close")["cover"] == 0.0


def test_reconcile_after_tp1_half_left_and_full_qty_stop_does_not_close(tmp_path):
    b = FB({S: {"side": "long", "qty": 0.5, "entry": 100.0}}, cover=1.0)       # TP filled, no TP order left
    x = bot2(b, tmp_path)
    x.reconcile(b.positions())
    assert not b.calls
    b.cover = 0.5                                                               # stop already resized
    x.reconcile(b.positions())
    assert not b.calls
    b.cover = 0.4                                                               # covers less than what is left
    x.reconcile(b.positions())
    assert b.calls == [("close", S)]


def test_reconcile_cancels_orders_of_a_vanished_position_and_drops_state(tmp_path):
    b = FB()
    x = bot2(b, tmp_path)
    x.state = {S: pos_state()}
    x.reconcile(b.positions())
    assert b.calls == [("cancel", S)] and x.state == {}
    assert Store(str(tmp_path / "v2.db")).last("v2_state")["pos"] == {}


def seed_fill(db, sym, side, qty, bot_fill=True):
    db.execute("INSERT INTO fills VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (int(time.time() * 1e6) % 10**9, sym, 1, CID if bot_fill else "web_1", "MARKET", side, 100, qty, 0, -0.01,
                int(time.time() * 1000), int(bot_fill)))


def test_hand_position_is_ignored_by_v2_reconcile_and_blocks_entry(tmp_path):
    b = FB({S: {"side": "long", "qty": 1.0, "entry": 100.0}}, cover=0.0)        # hand trade: no stops at all
    x = bot2(b, tmp_path, mode="demo")
    seed_fill(x.store.db, S, "buy", 1.0, bot_fill=False)
    x.reconcile(b.positions())
    assert not b.calls and x.mine(b.positions()) == {} and S in x.foreign
    x.enter(setup(), 100.0)
    assert not b.calls


# ---- trailing -----------------------------------------------------------------------------------------------------

def test_tp1_moves_the_stop_to_breakeven_on_the_remaining_qty(tmp_path):
    b = FB({S: {"side": "long", "qty": 0.5, "entry": 100.0}}, last=104.0)
    x = bot2(b, tmp_path)
    x.state = {S: pos_state()}
    x.trail()
    assert b.calls == [("move_stop", S, 100.0, 0.5)]
    assert x.state[S]["tp1_done"] and x.state[S]["stop"] == 100.0


def test_no_tp1_means_no_trailing(tmp_path):
    b = FB({S: {"side": "long", "qty": 1.0, "entry": 100.0}}, last=130.0)
    x = bot2(b, tmp_path)
    x.state = {S: pos_state()}
    x.trail()
    assert not b.calls and x.state[S]["stop"] == 95.0


def test_trailing_only_tightens(tmp_path):
    b = FB({S: {"side": "long", "qty": 0.5, "entry": 100.0}}, last=104.0)
    x = bot2(b, tmp_path)
    x.state = {S: pos_state(tp1_done=True, stop=100.0, extreme=104.0)}
    b.data.last = 110.0                                  # 110 - 2.5*2.5 = 103.75
    x.trail()
    assert b.calls == [("move_stop", S, 103.75, 0.5)]
    b.calls.clear()
    b.data.last = 107.0                                  # pullback: extreme stays 110, stop stays
    x.trail()
    b.data.last = 110.1                                  # +0.1 improves by 0.1 < 0.1 ATR (0.25): no churn
    x.trail()
    assert not b.calls and x.state[S]["stop"] == 103.75
    b.data.last = 112.0                                  # 112 - 6.25 = 105.75
    x.trail()
    assert b.calls == [("move_stop", S, 105.75, 0.5)]


def test_short_trailing_mirrors_long(tmp_path):
    b = FB({S: {"side": "short", "qty": 0.5, "entry": 100.0}}, last=90.0)
    x = bot2(b, tmp_path)
    x.state = {S: pos_state("short", stop=100.0, tp1_done=True, extreme=96.0)}
    x.trail()                                            # 90 + 6.25 = 96.25 (tighter than 100)
    assert b.calls == [("move_stop", S, 96.25, 0.5)]


def test_breakeven_already_breached_closes_instead_of_placing_a_dead_stop(tmp_path):
    b = FB({S: {"side": "long", "qty": 0.5, "entry": 100.0}}, last=99.0)       # TP filled, then price fell under entry
    x = bot2(b, tmp_path)
    x.state = {S: pos_state()}
    x.trail()
    assert b.calls == [("close", S)]


def test_committee_tighten_only_moves_in_the_safe_direction(tmp_path):
    class C:
        def __init__(self, res): self.res = res
        def manage(self, pos, ctx, store): return self.res
    b = FB({S: {"side": "long", "qty": 1.0, "entry": 100.0}}, last=104.0)
    x = bot2(b, tmp_path, arm="committee", committee=C({"action": "tighten", "new_stop": 90.0}))
    x.state = {S: pos_state()}
    x.manage_hourly()                                    # 90 < 95: would widen
    assert not b.calls
    x.committee = C({"action": "tighten", "new_stop": 98.0})
    x.manage_hourly()
    assert b.calls == [("move_stop", S, 98.0, 1.0)]
    x.committee = C({"action": "tighten", "new_stop": 105.0})   # above the price: refused by the breach rule -> close
    x.manage_hourly()
    assert b.calls[-1] == ("close", S)
    sig = bot2(FB(), tmp_path / "..", arm="signal", committee=C({"action": "close"}))
    sig.manage_hourly()                                  # signal arm never consults the committee
