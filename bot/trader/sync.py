"""Exchange -> SQLite sync: fills, income, live snapshot, LLM spend, equity ticks. All functions take Store.db.

Only fills whose order has a ccxt-broker clientOrderId (PREFIX) and happened after BOT_START belong to the bot;
the owner trades by hand on the same wallet and those trades must never reach a bot number or be touched.
"""
import csv
import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

from . import notify

log = logging.getLogger("sync")
PREFIX = "x-cvBPrNm9"
DAY, WEEK = 86_400_000, 7 * 86_400_000
# CSV rows are only trusted before the first API row, so an overlapping export is never double counted
INC_OK = "(source='api' OR time_ms < (SELECT COALESCE(MIN(time_ms), 9e18) FROM income WHERE source='api'))"


def bot_start_ms() -> int:
    s = os.getenv("BOT_START", "2026-11-27T06:25:00Z").replace("Z", "+00:00")
    return int(datetime.fromisoformat(s).timestamp() * 1000)


def raw(symbol: str) -> str:
    """'SOL/USDT:USDT' -> 'SOLUSDT' (the income table uses Binance ids)."""
    return symbol.split(":")[0].replace("/", "")


def cid(o: dict) -> str:
    i = o.get("info") or {}
    return str(o.get("clientOrderId") or i.get("clientOrderId") or i.get("clientAlgoId") or "")


def is_bot(o: dict) -> bool:
    return cid(o).startswith(PREFIX)


def init(db):
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    for ddl in (
        "CREATE TABLE IF NOT EXISTS fills(id INTEGER, symbol TEXT, order_id INTEGER, client_id TEXT, order_type TEXT,"
        " side TEXT, price REAL, qty REAL, realized REAL, fee REAL, time_ms INTEGER, bot INTEGER, PRIMARY KEY(symbol, id))",
        "CREATE TABLE IF NOT EXISTS income(tran_id TEXT, type TEXT, symbol TEXT, amount REAL, asset TEXT,"
        " time_ms INTEGER, source TEXT, PRIMARY KEY(tran_id, type, time_ms))",
        "CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT, ts INTEGER)",
        "CREATE TABLE IF NOT EXISTS ticks(time INTEGER PRIMARY KEY, value REAL, futures_value REAL, upnl REAL)",
    ):
        db.execute(ddl)


def set_state(db, key, value):
    db.execute("INSERT OR REPLACE INTO state VALUES (?, ?, ?)", (key, json.dumps(value), int(time.time())))


def get_state(db, key):
    r = db.execute("SELECT value, ts FROM state WHERE key = ?", (key,)).fetchone()
    return (json.loads(r[0]), r[1]) if r else None


# ---- income ---------------------------------------------------------------------------------------------------

def sync_income(ex, db, now_ms: int | None = None):
    now = now_ms or int(time.time() * 1000)
    last = db.execute("SELECT MAX(time_ms) FROM income WHERE source='api'").fetchone()[0]
    t = last + 1 if last else now - 90 * DAY
    while t <= now:
        end, cur = min(t + WEEK - 1, now), t
        while True:
            rows = ex.fapiPrivateGetIncome({"startTime": cur, "endTime": end, "limit": 1000})
            for r in rows:
                tid = f"{r.get('tranId', '')}:{r.get('tradeId', '')}"
                db.execute("INSERT OR IGNORE INTO income VALUES (?,?,?,?,?,?,'api')",
                           (tid, r["incomeType"], r.get("symbol") or "", float(r["income"]), r.get("asset") or "",
                            int(r["time"])))
            nxt = max((int(r["time"]) for r in rows), default=0) + 1
            if len(rows) < 1000 or nxt <= cur or nxt > end:
                break
            cur = nxt
        t = end + 1


def _ledger_type(s: str) -> str:
    k = re.sub(r"[^a-z]", "", s.lower())
    for needle, t in (("funding", "FUNDING_FEE"), ("realized", "REALIZED_PNL"), ("pnl", "REALIZED_PNL"),
                      ("commission", "COMMISSION"), ("fee", "COMMISSION"), ("transfer", "TRANSFER")):
        if needle in k:
            return t
    return re.sub(r"\W+", "_", s.strip()).upper()


def _csv_ms(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s) if int(s) > 10**11 else int(s) * 1000
    return int(datetime.fromisoformat(s.replace("/", "-")).replace(tzinfo=timezone.utc).timestamp() * 1000)


def import_income_csv(db, path: str) -> int:
    """Binance 'Futures - Transaction History' export. Returns the number of rows read."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        heads = {h.strip().lower(): h for h in rd.fieldnames or []}
        col = lambda *names: next((heads[n] for n in names if n in heads), None)
        c_time = col("date(utc)", "time(utc)", "date(utc+0)", "time", "date")
        c_type = col("type", "transaction type", "income type")
        c_amt = col("amount", "income")
        c_asset, c_sym, c_id = col("asset", "coin"), col("symbol"), col("transaction id", "tranid")
        if not (c_time and c_type and c_amt):
            raise ValueError(f"unrecognised CSV header: {list(heads)}")
        seen, n = Counter(), 0
        for r in rd:
            if not (r[c_time] or "").strip():
                continue
            ms, typ, amt = _csv_ms(r[c_time]), _ledger_type(r[c_type]), float(r[c_amt].replace(",", ""))
            sym = (r.get(c_sym) or "").strip() if c_sym else ""
            key = f"{ms}|{typ}|{amt}|{sym}"
            seen[key] += 1   # identical rows in one file stay distinct, and a re-import hits the same ids
            tid = (r.get(c_id) or "").strip() if c_id else ""
            tid = tid or hashlib.sha1(f"{key}|{seen[key]}".encode()).hexdigest()[:16]
            db.execute("INSERT OR IGNORE INTO income VALUES (?,?,?,?,?,?,'csv')",
                       (tid, typ, sym, amt, (r.get(c_asset) or "USDT").strip() if c_asset else "USDT", ms))
            n += 1
    return n


# ---- fills ----------------------------------------------------------------------------------------------------

def sync_fills(ex, db, symbols, bot_start: int, now_ms: int | None = None):
    now = now_ms or int(time.time() * 1000)
    syms = list(dict.fromkeys(symbols))
    by_id = getattr(ex, "markets_by_id", None) or {}
    for (rs,) in db.execute("SELECT DISTINCT symbol FROM income WHERE symbol != ''").fetchall():
        for m in by_id.get(rs) or []:
            if m["symbol"] not in syms and m.get("swap", True):
                syms.append(m["symbol"])
    for sym in syms:
        last = db.execute("SELECT MAX(time_ms) FROM fills WHERE symbol=?", (sym,)).fetchone()[0]
        t = last if last else bot_start - DAY
        while t <= now:
            end, cur = min(t + WEEK - 1, now), t
            # shortcut: orders are not paginated (>1000 orders in one window is far beyond this bot)
            orders = {int(o["info"]["orderId"]): o for o in
                      ex.fetch_orders(sym, cur, 1000, {"endTime": end})}
            while True:
                trades = ex.fetch_my_trades(sym, cur, 1000, {"endTime": end})
                for tr in trades:
                    i = tr["info"]
                    o = orders.get(int(i["orderId"]))
                    c = cid(o) if o else ""
                    typ = ((o or {}).get("info") or {}).get("origType") or ((o or {}).get("info") or {}).get("type") or ""
                    ms = int(i["time"])
                    db.execute("INSERT OR IGNORE INTO fills VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                               (int(i["id"]), sym, int(i["orderId"]), c, typ, i["side"].lower(), float(i["price"]),
                                float(i["qty"]), float(i.get("realizedPnl") or 0), -abs(float(i.get("commission") or 0)),
                                ms, int(c.startswith(PREFIX) and ms >= bot_start)))
                nxt = max((int(x["info"]["time"]) for x in trades), default=0)
                if len(trades) < 1000 or nxt <= cur:
                    break
                cur = nxt
            t = end + 1


def replay(db, bot_start: int):
    """Replay bot fills per symbol (one-way mode). Returns (closed trades oldest first, {symbol: open state})."""
    rows = db.execute("SELECT symbol, order_type, side, price, qty, realized, fee, time_ms FROM fills "
                      "WHERE bot=1 AND time_ms>=? ORDER BY time_ms, id", (bot_start,)).fetchall()
    decisions = [(ts, d.get("symbol"), d.get("action"), str(d.get("reason") or "")) for ts, d in
                 ((r[0], json.loads(r[1])) for r in db.execute("SELECT ts, data FROM events WHERE kind='decision'"))]
    trades, openp = [], {}
    for sym, typ, side, px, qty, rz, fee, t in rows:
        sgn = 1 if side == "buy" else -1
        o = openp.get(sym)
        if o is None:
            o = openp[sym] = {"side": "long" if sgn > 0 else "short", "net": 0.0, "t0": t, "iq": 0.0, "in": 0.0,
                              "oq": 0.0, "on": 0.0, "pnl": 0.0, "fees": 0.0}
        if (sgn > 0) == (o["side"] == "long"):
            o["iq"] += qty
            o["in"] += px * qty
        else:
            o["oq"] += qty
            o["on"] += px * qty
        o["net"] += sgn * qty   # shortcut: a fill flipping through zero is not split (the bot only sends reduce-only exits)
        o["pnl"] += rz
        o["fees"] += fee
        if abs(o["net"]) < 1e-9:
            del openp[sym]
            fund = db.execute(f"SELECT COALESCE(SUM(amount),0) FROM income WHERE type='FUNDING_FEE' AND symbol=? "
                              f"AND time_ms BETWEEN ? AND ? AND {INC_OK}", (raw(sym), o["t0"], t)).fetchone()[0]
            near = lambda ts, ms: abs(ts - ms / 1000) <= 120
            if typ in ("STOP_MARKET", "STOP"):
                why = "stop_loss"
            elif typ in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT"):
                why = "take_profit"
            elif any(s == sym and a == "close" and near(ts, t) for ts, s, a, _ in decisions):
                why = "llm_close"
            else:
                why = "close"
            trades.append({"symbol": sym, "side": o["side"], "qty": o["iq"], "entry": o["in"] / o["iq"],
                           "exit": o["on"] / o["oq"], "open_time": o["t0"], "close_time": t, "pnl": o["pnl"],
                           "fees": o["fees"], "funding": fund, "net": o["pnl"] + o["fees"] + fund, "reason": why,
                           "test": any(s == sym and r.lower().startswith("manual test") and near(ts, o["t0"])
                                       for ts, s, _, r in decisions)})
    return trades, openp


def bot_trades(db, bot_start: int) -> list[dict]:
    return replay(db, bot_start)[0]


def bot_open_qty(db, bot_start: int) -> dict:
    return {s: o["net"] for s, o in replay(db, bot_start)[1].items()}


# ---- snapshots ------------------------------------------------------------------------------------------------

def snapshot_live(ex, db, symbols):
    opens = replay(db, bot_start_ms())[1]
    f = lambda v: float(v) if v not in (None, "") else None
    out = []
    for p in ex.fetch_positions():
        c = float(p.get("contracts") or 0)
        if not c:
            continue
        sym = p["symbol"]
        o = opens.get(sym)
        mine = bool(o) and abs(o["net"] - (c if p["side"] == "long" else -c)) < 1e-9
        out.append({"symbol": sym, "side": p["side"], "qty": c, "entry": f(p.get("entryPrice")),
                    "mark": f(p.get("markPrice")), "upnl": f(p.get("unrealizedPnl")) or 0.0,
                    "roe_pct": f(p.get("percentage")), "liq": f(p.get("liquidationPrice")),
                    "opened": o["t0"] / 1000 if mine else None, "bot": mine, "sl": None, "tp": None})
    for p in out:
        if p["bot"] and p["symbol"] in symbols:
            for o in ex.fetch_open_orders(p["symbol"], params={"trigger": True}):
                if is_bot(o):
                    kind = str((o.get("info") or {}).get("origType") or o.get("type") or "").upper()
                    px = f(o.get("stopPrice") or o.get("triggerPrice"))
                    p["sl" if kind.startswith("STOP") else "tp" if kind.startswith("TAKE") else "sl"] = px
    info = ex.fetch_balance().get("info") or {}
    set_state(db, "live", {"ts": int(time.time()), "equity": f(info.get("totalMarginBalance")),
                           "wallet": f(info.get("totalWalletBalance")), "positions": out})


def snapshot_llm(db):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return
    r = httpx.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    r.raise_for_status()
    set_state(db, "llm", {"usage": float(r.json()["data"]["usage"])})


def values(db) -> dict:
    """The bot's own money: futures start + closed bot trades + open bot upnl, plus the LLM credit left."""
    sf, credit = float(os.getenv("START_FUTURES", "18.7392")), float(os.getenv("LLM_CREDIT", "2.0"))
    trades = bot_trades(db, bot_start_ms())
    live, llm = get_state(db, "live"), get_state(db, "llm")
    upnl = sum(p.get("upnl") or 0 for p in (live[0]["positions"] if live else []) if p.get("bot"))
    spent = max(0.0, llm[0]["usage"] - float(os.getenv("LLM_USAGE_BASELINE", "0.00267"))) if llm else 0.0
    fut = sf + sum(t["net"] for t in trades) + upnl
    return {"trades": trades, "start_futures": sf, "llm_credit": credit, "capital": sf + credit, "upnl": upnl,
            "futures_value": fut, "llm_spent": spent, "llm_remaining": credit - spent,
            "value": fut + credit - spent}


def tick(db, now: float | None = None):
    v = values(db)
    t = int(now or time.time()) // 300 * 300
    db.execute("INSERT OR REPLACE INTO ticks VALUES (?,?,?,?)", (t, v["value"], v["futures_value"], v["upnl"]))


def run(ex, db, symbols, last: dict, now: float | None = None):
    """One pass of the loop; each step has its own interval and failure never reaches the trading loop."""
    now = now or time.time()
    steps = (("fills", 120, lambda: sync_fills(ex, db, symbols, bot_start_ms())),
             ("income", 120, lambda: sync_income(ex, db)),
             ("live", 0, lambda: snapshot_live(ex, db, symbols)),
             ("llm", 600, lambda: snapshot_llm(db)),
             ("tick", 0, lambda: tick(db, now)))
    for name, every, fn in steps:
        if now - last.get(name, 0) < every:
            continue
        last[name] = now
        try:
            fn()
        except Exception as e:
            log.warning("sync %s: %s", name, notify.redact(f"{type(e).__name__}: {e}")[:200])


if __name__ == "__main__":
    import glob
    import sqlite3
    import sys
    if len(sys.argv) != 4 or sys.argv[1] != "import-csv":
        sys.exit("usage: python -m trader.sync import-csv <db> <file-or-dir>")
    conn = sqlite3.connect(sys.argv[2], isolation_level=None)
    init(conn)
    src = sys.argv[3]
    for f in sorted(glob.glob(os.path.join(src, "*.csv")) if os.path.isdir(src) else [src]):
        print(f"{f}: {import_income_csv(conn, f)} rows")
