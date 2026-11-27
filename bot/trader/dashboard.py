"""Read-only dashboard over the live bot database: python -m trader.dashboard  (port 8080, DASH_DBS=/data/live.db)
Static single-page UI in trader/static, JSON under /api/*; no exchange keys here (candles use public ccxt).

Public behind Caddy (trade.brandondev.online): login form with DASH_USER / DASH_PASSWORD, then a signed
HttpOnly session cookie (7 days). /health is the only public path.
"""
import hashlib
import hmac
import html
import os
import json
import mimetypes
import re
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sync

e = lambda v: html.escape(str(v))   # every value may come from an LLM or a news feed
STATIC = os.path.join(os.path.dirname(__file__), "static")
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT").split(",")
ICT = 7 * 3600   # Asia/Ho_Chi_Minh


SESSION_S = 7 * 24 * 3600
_fail_lock = threading.Lock()   # failed logins are serialized with a 1 s delay: ~1 guess/s at most


def _key() -> bytes:
    # changing DASH_PASSWORD invalidates every session
    return hmac.new(os.getenv("DASH_PASSWORD", "").encode(), b"session", hashlib.sha256).digest()


def credentials_ok(user: str, pw: str) -> bool:
    u, p = os.getenv("DASH_USER", ""), os.getenv("DASH_PASSWORD", "")
    if not (u and p):
        return False
    return hmac.compare_digest(f"{user}:{pw}".encode(), f"{u}:{p}".encode())


def make_session(now: float | None = None) -> str:
    exp = str(int((now or time.time()) + SESSION_S))
    return exp + "." + hmac.new(_key(), exp.encode(), hashlib.sha256).hexdigest()


def session_ok(cookie_header: str | None, now: float | None = None) -> bool:
    if not (cookie_header and os.getenv("DASH_PASSWORD")):
        return False
    c = SimpleCookie()
    try:
        c.load(cookie_header)
    except Exception:
        return False
    v = c["s"].value if "s" in c else ""
    exp, _, sig = v.partition(".")
    if not exp.isdigit() or int(exp) < (now or time.time()):
        return False
    return hmac.compare_digest(sig, hmac.new(_key(), exp.encode(), hashlib.sha256).hexdigest())


def login_page(error: str = "") -> str:
    msg = f"<p class=err>{e(error)}</p>" if error else ""
    return f"""<!doctype html><html lang=vi><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Bot Giao Dịch · Đăng nhập</title><link rel=icon href=/static/logo.svg type="image/svg+xml">
<link rel=apple-touch-icon href=/static/logo-180.png>
<style>body{{font:15px system-ui,-apple-system,"Segoe UI",sans-serif;background:#0b0e11;color:#eaecef;display:grid;place-items:center;min-height:100vh;margin:0}}
form{{background:#181a20;border:1px solid #2b3139;padding:32px 28px;border-radius:12px;width:min(340px,88vw);display:grid;gap:14px}}
.brand{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}.brand img{{width:36px;height:36px}}
.brand b{{font-size:20px;display:block}}.brand span{{font-size:12px;color:#848e9c}}
label{{display:grid;gap:6px;font-size:13px;color:#848e9c}}
input{{font:inherit;padding:11px 12px;border-radius:8px;border:1px solid #2b3139;background:#0b0e11;color:#eaecef}}
input:focus{{outline:none;border-color:#fcd535}}
button{{font:inherit;font-weight:600;padding:11px;border:0;border-radius:8px;background:#fcd535;color:#181a20;cursor:pointer}}
button:hover{{background:#f0b90b}}.err{{color:#f6465d;margin:0;font-size:13px}}</style>
<form method=post action=/login><div class=brand><img src=/static/logo.svg alt=""><div><b>Bot Giao Dịch</b><span>Binance Futures · AI</span></div></div>{msg}
<label>Tên đăng nhập<input name=user autocomplete=username required autofocus></label>
<label>Mật khẩu<input name=password type=password autocomplete=current-password required></label>
<button type=submit>Đăng nhập</button></form></html>"""


CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; form-action 'self'; frame-ancestors 'none'")
TFS = {"15m", "1h", "4h", "1d"}
_candle_cache: dict = {}
_pub = None


def _db():
    """Open the live DB; None while it or any table is missing (every endpoint then answers empty)."""
    path = (os.getenv("DASH_DBS", "").split(",")[0] or "/data/live.db")
    if not os.path.exists(path):
        return None
    db = sqlite3.connect(path, timeout=5)
    have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"events", "fills", "income", "state", "ticks"} <= have:
        db.close()
        return None
    return db


def _day(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(t + ICT))


def api_summary(db) -> dict:
    now = time.time()
    v = sync.values(db) if db else None
    if not v:
        return {}
    ticks = db.execute("SELECT time, value FROM ticks ORDER BY time").fetchall()
    start = sync.bot_start_ms() / 1000
    pts = [(start, v["capital"])] + ticks
    midnight = (now + ICT) // 86400 * 86400 - ICT
    base = next((x for t, x in reversed(pts) if t < midnight), pts[0][1])
    peak, dd = 0.0, 0.0
    for _, x in pts:
        peak = max(peak, x)
        dd = max(dd, (peak - x) / peak * 100 if peak else 0)
    tr = v["trades"]
    wins = sum(t["net"] > 0 for t in tr)
    return {"start": {"time": start, "futures": v["start_futures"], "llm_credit": v["llm_credit"], "capital": v["capital"]},
            "now": {"futures_value": v["futures_value"], "llm_remaining": v["llm_remaining"], "value": v["value"],
                    "pnl": v["value"] - v["capital"], "pnl_pct": (v["value"] - v["capital"]) / v["capital"] * 100,
                    "today_pnl": v["value"] - base if ticks else 0},
            "stats": {"trades": len(tr), "wins": wins, "win_rate": wins / len(tr) * 100 if tr else 0,
                      "realized": sum(t["pnl"] for t in tr), "fees": sum(t["fees"] for t in tr),
                      "funding": sum(t["funding"] for t in tr), "llm_spent": v["llm_spent"], "max_dd_pct": dd},
            "updated": int(now)}


def api_equity(db) -> dict:
    if not db:
        return {"points": [], "daily": []}
    cap = float(os.getenv("START_FUTURES", "18.7392")) + float(os.getenv("LLM_CREDIT", "2.0"))
    pts = [[sync.bot_start_ms() / 1000, cap]] + [[t, x] for t, x in db.execute("SELECT time, value FROM ticks ORDER BY time")]
    daily: dict = {}
    for t in sync.bot_trades(db, sync.bot_start_ms()):
        d = _day(t["close_time"] / 1000)
        daily[d] = daily.get(d, 0) + t["net"]
    return {"points": pts, "daily": sorted(daily.items())}


def api_live(db) -> dict:
    st = sync.get_state(db, "live") if db else None
    live = st[0] if st else {"ts": None, "equity": None, "wallet": None, "positions": []}
    ps = live["positions"]
    return {**live, "positions": [p for p in ps if p.get("bot")], "manual_positions": [p for p in ps if not p.get("bot")]}


def api_trades(db) -> list:
    if not db:
        return []
    return [{**t, "open_time": t["open_time"] / 1000, "close_time": t["close_time"] / 1000}
            for t in reversed(sync.bot_trades(db, sync.bot_start_ms()))]


def api_decisions(db, limit: int) -> list:
    if not db:
        return []
    out = []
    for ts, data in db.execute("SELECT ts, data FROM events WHERE kind='decision' ORDER BY rowid DESC LIMIT ?", (limit,)):
        d = json.loads(data)
        out.append({"time": ts, "symbol": d.get("symbol"), "action": d.get("action"), "confidence": d.get("confidence"),
                    "accepted": d.get("accepted"), "reject": d.get("reject"), "sl": d.get("stop_loss"),
                    "tp": d.get("take_profit"), "reason": d.get("reason")})
    return out


def api_candles(db, symbol: str, tf: str) -> dict:
    global _pub
    hit = _candle_cache.get((symbol, tf))
    if not hit or time.time() - hit[0] > 30:
        if _pub is None:
            import ccxt
            _pub = ccxt.binanceusdm({"enableRateLimit": True})
        _candle_cache[(symbol, tf)] = hit = (time.time(), _pub.fetch_ohlcv(symbol, tf, limit=200))
    candles = hit[1]
    markers = []
    if db and candles:
        t0 = candles[0][0] / 1000
        for t in sync.bot_trades(db, sync.bot_start_ms()):
            if t["symbol"] != symbol:
                continue
            buy = t["side"] == "long"
            for when, px, side, label in ((t["open_time"], t["entry"], buy, "Mở"), (t["close_time"], t["exit"], not buy, "Đóng")):
                if when / 1000 >= t0:
                    markers.append({"time": when / 1000, "side": "buy" if side else "sell", "price": px, "label": label})
        st = sync.get_state(db, "live")
        for p in (st[0]["positions"] if st else []):
            if p.get("bot") and p["symbol"] == symbol and p.get("opened") and p["opened"] >= t0:
                markers.append({"time": p["opened"], "side": "buy" if p["side"] == "long" else "sell",
                                "price": p["entry"], "label": "Mở"})
    return {"candles": [[c[0] / 1000] + c[1:6] for c in candles], "markers": markers}


def api_account(db) -> dict:
    empty = {"coverage": {"from": None, "to": None, "sources": []},
             "totals": dict.fromkeys(("transfer_in", "transfer_out", "realized", "fees", "funding", "net"), 0),
             "monthly": [], "by_symbol": [], "fills": []}
    if not db:
        return empty
    rows = db.execute(f"SELECT type, symbol, amount, time_ms FROM income WHERE {sync.INC_OK}").fetchall()
    lo, hi = db.execute(f"SELECT MIN(time_ms), MAX(time_ms) FROM income WHERE {sync.INC_OK}").fetchone()
    srcs = [r[0] for r in db.execute(f"SELECT DISTINCT source FROM income WHERE {sync.INC_OK}")]
    col = {"REALIZED_PNL": 0, "COMMISSION": 1, "FUNDING_FEE": 2}
    tot, mon, sym = {"transfer_in": 0.0, "transfer_out": 0.0}, {}, {}
    for typ, s, amt, ms in rows:
        if typ == "TRANSFER":
            tot["transfer_in" if amt > 0 else "transfer_out"] += abs(amt)
            continue
        i = col.get(typ, 3)   # other trading income (e.g. INSURANCE_CLEAR) counts into net only
        for bucket in (mon.setdefault(_day(ms / 1000)[:7], [0.0] * 4), sym.setdefault(s, [0.0] * 4)):
            bucket[i] += amt
    fills = db.execute("SELECT time_ms, symbol, side, price, qty, realized, fee, bot FROM fills "
                       "ORDER BY time_ms DESC LIMIT 500").fetchall()
    cnt: dict = {}
    for f in db.execute("SELECT symbol FROM fills"):
        cnt[sync.raw(f[0])] = cnt.get(sync.raw(f[0]), 0) + 1
    tot.update(realized=sum(v[0] for v in mon.values()), fees=sum(v[1] for v in mon.values()),
               funding=sum(v[2] for v in mon.values()))
    tot["net"] = sum(sum(v) for v in mon.values())
    return {"coverage": {"from": lo / 1000 if lo else None, "to": hi / 1000 if hi else None, "sources": srcs},
            "totals": tot,
            "monthly": [[m, *v[:3], sum(v)] for m, v in sorted(mon.items())],
            "by_symbol": [{"symbol": s, "realized": v[0], "fees": v[1], "funding": v[2], "net": sum(v),
                           "fills": cnt.get(s, 0)} for s, v in sorted(sym.items()) if s],
            "fills": [{"time": f[0] / 1000, "symbol": f[1], "side": f[2], "price": f[3], "qty": f[4],
                       "realized": f[5], "fee": f[6], "bot": bool(f[7])} for f in fills]}



class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str = "", headers: dict | None = None):
        out = body.encode()
        self.send_response(code)
        if "Content-Type" not in (headers or {}):
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def _cookie(self, value: str, max_age: int) -> str:
        secure = "" if os.getenv("DASH_INSECURE_COOKIE") == "1" else "; Secure"   # tests run on plain http
        return f"s={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict{secure}"

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, default=str), {"Content-Type": "application/json"})

    def _file(self, path: str):
        with open(path, "rb") as f:
            out = f.read()
        self.send_response(200)
        self.send_header("Content-Type", {".woff2": "font/woff2", ".js": "text/javascript"}.get(
            os.path.splitext(path)[1], mimetypes.guess_type(path)[0] or "application/octet-stream"))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/health":   # public liveness probe, no data
            return self._send(200, "ok")
        if path == "/login":
            return self._send(200, login_page())
        if path in ("/static/logo.svg", "/static/logo-180.png", "/favicon.ico"):   # public: the login page shows them
            return self._file(os.path.join(STATIC, "logo.svg" if path == "/favicon.ico" else path[8:]))
        authed = session_ok(self.headers.get("Cookie"))
        if path.startswith("/api/"):
            if not authed:
                return self._json(401, {"error": "login required"})
            return self._api(path, q)
        if not authed:
            return self._send(303, "", {"Location": "/login"})
        if path == "/":
            return self._file(os.path.join(STATIC, "index.html"))
        name = path[len("/static/"):] if path.startswith("/static/") else ""
        if re.fullmatch(r"[A-Za-z0-9_.-]+", name) and name not in (".", "..") and os.path.isfile(os.path.join(STATIC, name)):
            return self._file(os.path.join(STATIC, name))
        self._send(404, "not found")

    def _api(self, path: str, q: dict):
        db = None
        try:
            if path == "/api/candles":
                sym, tf = q.get("symbol", [""])[0], q.get("tf", [""])[0]
                if sym not in SYMBOLS or tf not in TFS:
                    return self._json(400, {"error": "bad symbol or tf"})
            db = _db()
            if path == "/api/summary":
                return self._json(200, api_summary(db))
            if path == "/api/equity":
                return self._json(200, api_equity(db))
            if path == "/api/live":
                return self._json(200, api_live(db))
            if path == "/api/trades":
                return self._json(200, api_trades(db))
            if path == "/api/decisions":
                lim = q.get("limit", ["300"])[0]
                return self._json(200, api_decisions(db, min(int(lim), 2000) if lim.isdigit() and int(lim) > 0 else 300))
            if path == "/api/candles":
                return self._json(200, api_candles(db, sym, tf))
            if path == "/api/account":
                return self._json(200, api_account(db))
            self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(500, {"error": type(e).__name__})
        finally:
            if db:
                db.close()

    def do_POST(self):
        path = self.path.split("?")[0]
        origin = self.headers.get("Origin")
        if origin and origin.split("://")[-1] != self.headers.get("Host"):   # cross-site form post
            return self._send(403, "forbidden")
        if path == "/logout":
            return self._send(303, "", {"Location": "/login", "Set-Cookie": self._cookie("", 0)})
        if path != "/login":
            return self._send(404, "not found")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4096:
            return self._send(413, "too large")
        form = parse_qs(self.rfile.read(n).decode(errors="replace"))
        if credentials_ok(form.get("user", [""])[0], form.get("password", [""])[0]):
            return self._send(303, "", {"Location": "/", "Set-Cookie": self._cookie(make_session(), SESSION_S)})
        with _fail_lock:
            time.sleep(1)
        self._send(401, login_page("Sai tên đăng nhập hoặc mật khẩu"))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(os.getenv("DASH_PASSWORD", "")) < 16:
        raise SystemExit("DASH_PASSWORD must be set (16+ chars)")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
