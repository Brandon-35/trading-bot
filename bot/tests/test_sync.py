"""Fill replay, hand-trade exclusion, CSV import and the JSON API over a real HTTP server (no network)."""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from trader import dashboard, sync
from trader.store import Store

S = "SOL/USDT:USDT"
T0 = 1_795_000_000_000   # ms
START = T0 - 1000


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_START", "2026-11-27T06:25:00Z")
    st = Store(str(tmp_path / "t.db"))
    sync.init(st.db)
    st.db.execute("PRAGMA journal_mode")
    return st


_i = [0]


def fill(db, side, qty, px, t, rz=0.0, typ="MARKET", bot=1, sym=S):
    _i[0] += 1
    db.execute("INSERT INTO fills VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (_i[0], sym, _i[0], "x-cvBPrNm9q" if bot else "web", typ, side, px, qty, rz, -0.01, t, bot))


def test_replay_win_loss_partial_sl_test_funding_and_hand(db):
    d = db.db
    fill(d, "buy", 1, 100, T0)
    fill(d, "sell", 0.4, 110, T0 + 1000, rz=4)             # partial close
    fill(d, "sell", 0.6, 112, T0 + 2000, rz=7.2)           # closes: win
    fill(d, "sell", 1, 100, T0 + 300_000)                  # short
    fill(d, "buy", 1, 103, T0 + 301_000, rz=-3, typ="STOP_MARKET")   # loss via SL
    fill(d, "buy", 5, 100, T0 + 320_000, bot=0)              # hand trade, ignored
    fill(d, "buy", 2, 100, T0 + 330_000)                   # still open
    d.execute("INSERT INTO income VALUES ('1:1','FUNDING_FEE','SOLUSDT',-0.05,'USDT',?, 'api')", (T0 + 500,))
    d.execute("INSERT INTO income VALUES ('2:2','FUNDING_FEE','SOLUSDT',-9,'USDT',?, 'api')", (T0 + 5000,))   # outside
    d.execute("INSERT INTO events VALUES (?, 'decision', ?)", (T0 // 1000, json.dumps(
        {"symbol": S, "action": "long", "reason": "Manual test entry"})))
    tr = sync.bot_trades(d, START)
    assert len(tr) == 2
    w, l = tr
    assert w["side"] == "long" and w["qty"] == 1 and w["exit"] == pytest.approx(111.2) and w["pnl"] == pytest.approx(11.2)
    assert w["funding"] == -0.05 and w["fees"] == pytest.approx(-0.03) and w["net"] == pytest.approx(11.12)
    assert w["test"] and w["reason"] == "close"
    assert l["reason"] == "stop_loss" and l["net"] < 0 and not l["test"]
    assert sync.bot_open_qty(d, START) == {S: 2}


def test_llm_close_reason(db):
    d = db.db
    fill(d, "buy", 1, 100, T0)
    fill(d, "sell", 1, 101, T0 + 1000, rz=1)
    d.execute("INSERT INTO events VALUES (?, 'decision', ?)", (T0 // 1000 + 2, json.dumps({"symbol": S, "action": "close"})))
    assert sync.bot_trades(d, START)[0]["reason"] == "llm_close"


def test_csv_import_real_header_with_bom(db, tmp_path):
    f = tmp_path / "x.csv"
    f.write_bytes(('﻿"Date(UTC)","type","Amount","Asset","Symbol","Transaction ID"\n'
                   '"2025-11-27 06:07:28","REALIZED_PNL","0.52","USDT","SOLUSDT","111"\n'
                   '"2025-11-27 06:07:28","COMMISSION","-0.01","USDT","SOLUSDT","111"\n'
                   '"2025-11-28 01:00:00","TRANSFER","20","USDT","","222"\n').encode())
    assert sync.import_income_csv(db.db, str(f)) == 3
    assert sync.import_income_csv(db.db, str(f)) == 3           # idempotent
    assert db.db.execute("SELECT COUNT(*), SUM(amount) FROM income").fetchone() == (3, pytest.approx(20.51))
    assert db.db.execute("SELECT tran_id FROM income WHERE type='TRANSFER'").fetchone()[0] == "222"
    f.write_text("Time,Transaction Type,Amount,Coin\n2025-11-29 00:00:00,Funding Fee,-0.1,USDT\n")
    sync.import_income_csv(db.db, str(f))
    assert db.db.execute("SELECT type FROM income WHERE amount=-0.1").fetchone()[0] == "FUNDING_FEE"


class FakeEx:
    markets_by_id = {}

    def fetch_orders(self, sym, since, limit, params):
        return [{"info": {"orderId": "7", "clientOrderId": "x-cvBPrNm9a", "origType": "TAKE_PROFIT_MARKET"}}]

    def fetch_my_trades(self, sym, since, limit, params):
        return [{"info": {"id": "1", "orderId": "7", "side": "SELL", "price": "100", "qty": "1",
                          "realizedPnl": "2", "commission": "0.01", "time": str(START + 5)}},
                {"info": {"id": "2", "orderId": "8", "side": "BUY", "price": "100", "qty": "1",
                          "realizedPnl": "0", "commission": "0.01", "time": str(START + 6)}}]


def test_sync_fills_flags_bot_by_prefix(db):
    sync.sync_fills(FakeEx(), db.db, [S], START, now_ms=START + 100)
    rows = db.db.execute("SELECT id, bot, order_type, fee FROM fills ORDER BY id").fetchall()
    assert rows == [(1, 1, "TAKE_PROFIT_MARKET", -0.01), (2, 0, "", -0.01)]


# ---- HTTP API ----------------------------------------------------------------------------------------------------

@pytest.fixture
def server(db, tmp_path, monkeypatch):
    now = time.time()
    st = int(sync.bot_start_ms())
    d = db.db
    fill(d, "buy", 1, 100, st + 1000)
    fill(d, "sell", 1, 110, st + 2000, rz=10)
    fill(d, "buy", 3, 100, st + 3000, bot=0)
    d.execute("INSERT INTO income VALUES ('9:9','TRANSFER','',20,'USDT',?,'api')", (st - 5000,))
    d.execute("INSERT INTO income VALUES ('3:3','REALIZED_PNL','SOLUSDT',10,'USDT',?,'api')", (st + 2000,))
    d.execute("INSERT INTO ticks VALUES (?,?,?,?)", (int(now) // 300 * 300, 21.0, 19.0, 0.1))
    d.execute("INSERT INTO events VALUES (?, 'decision', ?)", (int(now), json.dumps(
        {"symbol": S, "action": "long", "confidence": 0.7, "accepted": False, "reject": "rr", "stop_loss": 1,
         "take_profit": 2, "reason": "<b>x</b>"})))
    sync.set_state(d, "live", {"ts": 1, "equity": 20, "wallet": 20, "positions": [
        {"symbol": S, "bot": True, "upnl": 0.1}, {"symbol": "BTC/USDT:USDT", "bot": False, "upnl": 5}]})
    sync.set_state(d, "llm", {"usage": 0.1})
    monkeypatch.setenv("DASH_DBS", str(tmp_path / "t.db"))
    monkeypatch.setenv("DASH_USER", "u")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    monkeypatch.setattr(dashboard, "_pub", type("P", (), {"fetch_ohlcv": lambda s, sym, tf, limit: [[st, 1, 2, 0, 1, 5]]})())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def get(base, path, auth=True):
    req = urllib.request.Request(base + path)
    if auth:
        req.add_header("Cookie", f"s={dashboard.make_session()}")
    try:
        r = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        r = e
    return r.status if hasattr(r, "status") else r.code, r.headers, r.read()


def test_api_endpoints(server):
    for p in ("/api/summary", "/api/equity", "/api/live", "/api/trades", "/api/decisions", "/api/account",
              "/api/candles?symbol=SOL/USDT:USDT&tf=1h"):
        assert get(server, p, auth=False)[0] == 401, p
        assert get(server, p)[0] == 200, p
    j = lambda p: json.loads(get(server, p)[2])
    s = j("/api/summary")
    assert s["stats"]["trades"] == 1 and s["stats"]["wins"] == 1 and s["stats"]["win_rate"] == 100
    assert s["start"]["capital"] == pytest.approx(20.7392)
    assert s["now"]["futures_value"] == pytest.approx(18.7392 + 9.98 + 0.1)   # 10 - two 0.01 fees
    assert j("/api/live")["manual_positions"][0]["symbol"] == "BTC/USDT:USDT" and len(j("/api/live")["positions"]) == 1
    t = j("/api/trades")
    assert len(t) == 1 and t[0]["entry"] == 100 and t[0]["open_time"] < 2e9
    assert j("/api/decisions?limit=5")[0]["reject"] == "rr"
    a = j("/api/account")
    assert a["totals"]["transfer_in"] == 20 and a["totals"]["realized"] == 10 and a["fills"][0]["bot"] is False
    c = j("/api/candles?symbol=SOL/USDT:USDT&tf=1h")
    assert len(c["candles"]) == 1 and len(c["markers"]) == 2
    assert get(server, "/api/candles?symbol=DOGE&tf=1h")[0] == 400
    assert get(server, "/api/candles?symbol=SOL/USDT:USDT&tf=5m")[0] == 400
    assert j("/api/equity")["points"][0][1] == pytest.approx(20.7392)


def test_empty_db_and_static(server, tmp_path, monkeypatch):
    code, h, body = get(server, "/")
    assert code == 200 and "script-src 'self'" in h["Content-Security-Policy"]
    assert "Đăng nhập".encode() in get(server, "/", auth=False)[2]   # redirected to /login
    assert get(server, "/static/app.js")[1]["Content-Type"].startswith("text/javascript")
    assert get(server, "/static/app.css")[1]["Cache-Control"] == "no-cache"
    for bad in ("/static/../dashboard.py", "/static/%2e%2e/x", "/static/..%2fdashboard.py", "/static/nope.js"):
        assert get(server, bad)[0] == 404, bad
    monkeypatch.setenv("DASH_DBS", str(tmp_path / "missing.db"))
    assert json.loads(get(server, "/api/trades")[2]) == []
    assert get(server, "/api/summary")[0] == 200
