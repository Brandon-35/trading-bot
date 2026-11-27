import json
import time

from trader import committee, llm
from trader.store import Store

SETUP = {"symbol": "SOL/USDT:USDT", "side": "long", "price": 140.0, "atr": 3.0, "stop_dist": 6.0, "signal": "breakout",
         "bar_time": 1, "features": {"rsi": 58.123456, "ema20": 138.5}}
CTX = {"btc": {"trend": "up"}, "derivs": {"funding": 0.0001}, "news": ["x"], "fear_greed": 55, "equity": 18.0,
       "open_positions": []}
LEAD_OK = {"action": "open", "side": "long", "confidence": 0.7, "sl_atr": 2.0, "tp_r": 2.5, "rationale": "ok"}
ANALYST = {"stance": "long", "confidence": 0.6, "key_points": ["a", "b", "c", "d", "e"]}
ARG = {"argument": "arg", "strongest_point": "sp"}


def fake(lead=LEAD_OK, analyst=ANALYST, calls=None, cost=0.001):
    def chat(model, messages, max_tokens=600, temperature=0.3, json_mode=True):
        sysmsg = messages[0]["content"]
        if calls is not None:
            calls.append(model)
        if "lead trader" in sysmsg:
            out = lead
        elif "technical analyst" in sysmsg or "analyst of" in sysmsg:
            out = analyst
        elif "review one open" in sysmsg:
            out = lead
        else:
            out = ARG
        if isinstance(out, Exception):
            raise out
        return (out if isinstance(out, str) else json.dumps(out)), cost
    return chat


def st(tmp_path):
    return Store(str(tmp_path / "s.db"))


def test_happy_path_open_and_events(tmp_path):
    s = st(tmp_path)
    r = committee.decide(SETUP, CTX, [], s, chat=fake())
    assert r["action"] == "open" and r["side"] == "long" and r["sl_atr"] == 2.0 and r["tp_r"] == 2.5
    assert abs(r["cost"] - 0.006) < 1e-9   # 3 analysts + bull + bear + lead
    assert len(s.all("llm_cost")) == 6 and len(s.all("debate")) == 1
    assert len(r["transcript"]["analysts"]["technical"]["key_points"]) == 4
    assert s.last("debate")["action"] == "open"


def test_lead_side_mismatch_and_low_confidence_skip(tmp_path):
    assert committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(LEAD_OK | {"side": "short"}))["action"] == "skip"
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(LEAD_OK | {"confidence": 0.59}))
    assert r["action"] == "skip" and "low confidence" in r["rationale"]


def test_bad_analyst_tolerated_lead_runs(tmp_path):
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(analyst="not json"))
    assert r["action"] == "open"
    assert r["transcript"]["analysts"]["news"] == {"unavailable": "JSONDecodeError"}


def test_lead_error_skips(tmp_path):
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(lead=RuntimeError("boom")))
    assert r["action"] == "skip" and r["rationale"] == "error: RuntimeError"
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(lead={"action": "maybe"}))
    assert r["rationale"] == "error: ValidationError"


def test_budget_exceeded_makes_no_call(tmp_path):
    s = st(tmp_path)
    s.log("llm_cost", usd=0.11, model="m", purpose="p")
    calls = []
    r = committee.decide(SETUP, CTX, [], s, chat=fake(calls=calls))
    assert r["action"] == "skip" and r["rationale"] == "budget" and calls == []
    s.db.execute("UPDATE events SET ts = ?", (int(time.time()) - 2 * 86400,))   # yesterday's spend does not count
    assert committee.Budget(s).ok()


def test_clamping(tmp_path):
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(LEAD_OK | {"sl_atr": 9, "tp_r": 0.5}))
    assert (r["sl_atr"], r["tp_r"]) == (3.0, 1.5)
    r = committee.decide(SETUP, CTX, [], st(tmp_path), chat=fake(LEAD_OK | {"sl_atr": 0.1, "tp_r": 10}))
    assert (r["sl_atr"], r["tp_r"]) == (1.0, 4.0)


def mg(action, new_stop=None):
    return fake({"action": action, "new_stop": new_stop, "rationale": "r"})


def test_manage(tmp_path):
    s = st(tmp_path)
    pos = {"side": "long", "mark": 100.0, "stop": 95.0}
    assert committee.manage(pos, CTX, s, chat=mg("tighten", 93.0))["action"] == "hold"   # widen
    assert committee.manage(pos, CTX, s, chat=mg("tighten", 101.0))["action"] == "hold"   # past the price
    assert committee.manage(pos, CTX, s, chat=mg("tighten", 97.0)) == {"action": "tighten", "new_stop": 97.0, "rationale": "r"}
    assert committee.manage(pos, CTX, s, chat=mg("close"))["action"] == "close"
    short = {"side": "short", "mark": 100.0, "stop": 105.0}
    assert committee.manage(short, CTX, s, chat=mg("tighten", 103.0))["action"] == "tighten"
    assert committee.manage(short, CTX, s, chat=mg("tighten", 107.0))["action"] == "hold"
    assert committee.manage(pos, CTX, s, chat=fake(RuntimeError()))["action"] == "hold"
    assert len(s.all("llm_cost")) == 6


def test_chat_cost_falls_back_to_price_table(monkeypatch):
    class U:
        prompt_tokens, completion_tokens = 1_000_000, 1_000_000

    class R:
        usage = U()
        choices = [type("C", (), {"message": type("M", (), {"content": "{}"})()})()]

    class Client:
        chat = type("X", (), {"completions": type("Y", (), {"create": staticmethod(lambda **k: R())})()})()

    monkeypatch.setattr(llm, "_client", lambda: Client())
    assert llm.chat("deepseek/deepseek-v3.2", [])[1] == 0.26 + 0.38
    U.cost = 0.0123
    assert llm.chat("deepseek/deepseek-v3.2", [])[1] == 0.0123


def test_chat_retries_once_on_5xx(monkeypatch):
    import httpx
    from openai import InternalServerError
    n = []

    def create(**k):
        n.append(1)
        raise InternalServerError("x", response=httpx.Response(500, request=httpx.Request("POST", "http://x")), body=None)

    client = type("C", (), {"chat": type("X", (), {"completions": type("Y", (), {"create": staticmethod(create)})()})()})()
    monkeypatch.setattr(llm, "_client", lambda: client)
    try:
        llm.chat("m", [])
        raise AssertionError
    except InternalServerError:
        assert len(n) == 2
