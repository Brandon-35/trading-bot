"""Bot decisions against a fake broker: bad LLM output must never reach the exchange."""
import os

os.environ.setdefault("LLM_MODEL", "x")
os.environ.setdefault("LLM_BASE_URL", "http://localhost")
os.environ.setdefault("LLM_API_KEY", "x")

import pytest

from trader import main as m
from trader.llm import LLM, Decision
from trader.risk import Limits
from trader.store import Store

S = "BTC/USDT:USDT"
REF = {S: {"price": 60_000.0, "atr": 600.0}}


class FakeBroker:
    def __init__(self, positions=None, protective=2):
        self.pos, self.protective, self.calls = positions or {}, protective, []

    def positions(self): return dict(self.pos)
    def free_margin(self): return 100.0
    def protective_count(self, s): return self.protective if s in self.pos else 0
    def cancel_protective(self, s): self.calls.append(("cancel", s))
    def market(self, s): return {"precision": {"amount": 0.001}, "limits": {"amount": {"min": 0.001}, "cost": {"min": 50}}}
    def open(self, *a): self.calls.append(("open",) + a)
    def close(self, s): self.calls.append(("close", s)); self.pos.pop(s, None)


def bot(broker, tmp_path, mode="paper"):
    return m.Bot(broker, None, Store(str(tmp_path / "t.db")), Limits(), mode)


def d(**k):
    base = dict(symbol=S, action="long", stop_loss=59_000, take_profit=62_000, confidence=0.7, reason="t")
    return Decision(**(base | k))


@pytest.mark.parametrize("bad, why", [
    (dict(stop_loss=None), "missing"),
    (dict(stop_loss=61_000), "wrong side"),
    (dict(take_profit=61_000), "reward/risk"),        # RR 1.0
    (dict(confidence=0.3), "confidence"),
    (dict(symbol="DOGE/USDT:USDT"), "not allowed"),
])
def test_bad_entries_place_no_order(tmp_path, bad, why):
    b = FakeBroker()
    reason = bot(b, tmp_path).act(d(**bad), {}, REF, 100.0, None)
    assert why in reason and not b.calls


def test_good_entry_is_sized_and_sent(tmp_path):
    b = FakeBroker()
    assert bot(b, tmp_path).act(d(), {}, REF, 100.0, None) is None
    assert b.calls == [("open", S, "long", 0.002, 59_000, 62_000)]


def test_daily_stop_and_limits_block_entries(tmp_path):
    b = FakeBroker()
    x = bot(b, tmp_path)
    assert "daily" in x.act(d(), {}, REF, 100.0, "daily")
    assert "already open" in x.act(d(), {S: {}}, REF, 100.0, None)
    assert "max positions" in x.act(d(), {"A": {}, "B": {}}, REF, 100.0, None)
    assert not b.calls


def test_reconcile_closes_unprotected_and_cancels_orphans(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "SYMBOLS", [S, "ETH/USDT:USDT"])
    b = FakeBroker({S: {"side": "long", "qty": 0.002, "entry": 60_000}}, protective=1)
    b.protective_count = lambda s: 1                    # S has only its TP; ETH has an orphan order
    bot(b, tmp_path, mode="demo").reconcile(b.positions())
    assert ("close", S) in b.calls and ("cancel", "ETH/USDT:USDT") in b.calls


def test_halt_persists_until_cleared(tmp_path):
    st = Store(str(tmp_path / "h.db"))
    assert not m.halted(st)
    st.log("halt", equity=69)
    assert m.halted(st)
    st.log("halt_clear")
    assert not m.halted(st)


def test_llm_garbage_means_hold(monkeypatch):
    llm = LLM()

    class R:
        usage = None
        choices = [type("C", (), {"message": type("M", (), {"content": "not json {"})()})()]

    monkeypatch.setattr(llm.client.chat.completions, "create", lambda **k: R())
    ds, meta = llm.decide({})
    assert ds == [] and "invalid reply" in meta["error"]
