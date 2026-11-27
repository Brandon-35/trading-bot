import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from trader import dashboard
from trader.store import Store


def seed(path, rs, committee=False):
    s = Store(path)
    t0 = int(time.time()) - 10000
    for i, r in enumerate(rs):
        s.db.execute("INSERT INTO events VALUES (?,?,?)", (t0 + i * 100, "trade_open", json.dumps({"symbol": "SOL/USDT:USDT"})))
        s.db.execute("INSERT INTO events VALUES (?,?,?)", (t0 + i * 100 + 50, "trade_close", json.dumps(
            {"symbol": "SOL/USDT:USDT", "side": "long", "qty": 1.0, "entry": 100, "exit": 101, "why": "stop_loss",
             "pnl": r * 0.4, "fees": 0.01, "funding": 0.0, "r": r})))
    s.log("equity", equity=19.5, positions={})
    s.log("paper_state", cash=1, last_funding_hour=0, pos={"ETH/USDT:USDT": {"side": "short", "qty": 0.5, "entry": 3000, "sl": 3100, "tp": 2800}})
    s.log("v2_scan", key=1)
    s.log("setup", symbol="ETH/USDT:USDT", bar_time=1, side="short", signal="breakout", price=3000, atr=10)
    if committee:
        s.log("llm_cost", usd=0.002, model="m", purpose="lead")
        s.log("debate", action="open", side="short", confidence=0.7, sl_atr=2.0, tp_r=2.5, rationale="why", cost=0.004,
              symbol="ETH/USDT:USDT", transcript={"analysts": {"technical": {"stance": "short", "confidence": 0.6, "key_points": ["a"]},
                                                              "news": {"unavailable": "Timeout"}},
                                                  "bull": {"argument": "up", "strongest_point": "x"},
                                                  "bear": {"argument": "down", "strongest_point": "y"}})
        s.log("debate", action="skip", side="long", confidence=0.0, sl_atr=2, tp_r=2, rationale="budget", cost=0, symbol="BTC/USDT:USDT", transcript={})


@pytest.fixture
def srv(tmp_path, monkeypatch):
    seed(str(tmp_path / "s.db"), [1.0, -1.0, 0.5, 2.0])
    seed(str(tmp_path / "c.db"), [1.0] * 30, committee=True)
    monkeypatch.setenv("ARM_DBS", f"signal={tmp_path}/s.db,committee={tmp_path}/c.db")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    monkeypatch.setenv("DASH_USER", "u")
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def get(base, path, auth=True):
    req = urllib.request.Request(base + path)
    if auth:
        req.add_header("Cookie", "s=" + dashboard.make_session())
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_auth_required(srv):
    for p in ("/api/arms", "/api/arm_trades?arm=signal", "/api/debates"):
        assert get(srv, p, auth=False)[0] == 401


def test_arms_aggregates(srv):
    code, d = get(srv, "/api/arms")
    assert code == 200
    sig, com = d["arms"]
    assert (sig["name"], com["name"]) == ("signal", "committee")
    assert sig["trades"] == 4 and sig["wins"] == 3 and sig["win_rate"] == 75
    assert sig["avg_r"] == pytest.approx(0.625) and not sig["edge_gate"]["passed"] and sig["risk_pct"] == 2
    assert com["edge_gate"] == {"trades_needed": 30, "trades": 30, "avg_r": 1.0, "passed": True} and com["risk_pct"] == 3
    assert com["equity"] == 19.5 and com["open"][0]["symbol"] == "ETH/USDT:USDT" and com["open"][0]["stop"] == 3100
    assert len(com["curve"]) == 31 and com["curve"][0][1] == 18.7392
    assert com["last_scan"]["setups"] == 1 and com["llm_total"] == pytest.approx(0.002) and sig["llm_total"] == 0
    assert sig["max_dd_pct"] > 0


def test_arm_trades(srv):
    code, tr = get(srv, "/api/arm_trades?arm=signal")
    assert code == 200 and len(tr) == 4 and tr[0]["close_time"] > tr[-1]["close_time"]
    assert tr[0]["net"] == pytest.approx(0.8) and tr[0]["open_time"] < tr[0]["close_time"] and tr[0]["r"] == 2.0
    assert get(srv, "/api/arm_trades?arm=nope")[0] == 400


def test_debates(srv):
    code, d = get(srv, "/api/debates?limit=1")
    assert code == 200 and len(d) == 1
    code, d = get(srv, "/api/debates")
    by = {x["symbol"]: x for x in d}
    e = by["ETH/USDT:USDT"]
    assert e["action"] == "open" and e["signal"] == "breakout" and e["analysts"]["technical"]["stance"] == "short"
    assert e["analysts"]["news"] == {"unavailable": "Timeout"} and e["bull"]["argument"] == "up"
    assert by["BTC/USDT:USDT"]["bull"] is None


def test_missing_dbs_are_empty(monkeypatch, tmp_path):
    (tmp_path / "bad.db").write_text("not sqlite")
    monkeypatch.setenv("ARM_DBS", f"signal={tmp_path}/none.db,committee={tmp_path}/bad.db")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    code, d = get(base, "/api/arms")
    assert code == 200 and all(a["trades"] == 0 and a["equity"] == a["start"] and a["last_scan"] is None for a in d["arms"])
    assert get(base, "/api/debates") == (200, []) and get(base, "/api/arm_trades?arm=signal") == (200, [])
    server.shutdown()
