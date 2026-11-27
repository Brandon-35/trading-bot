"""Read-only status page over the bot databases: python -m trader.dashboard  (port 8080, DASH_DBS=/data/live.db,...)

Public behind Caddy (trade.brandondev.online): login form with DASH_USER / DASH_PASSWORD, then a signed
HttpOnly session cookie (7 days). /health is the only public path.
"""
import glob
import hashlib
import hmac
import html
import os
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .main import halted
from .report import stats
from .store import Store

e = lambda v: html.escape(str(v))   # every value may come from an LLM or a news feed
ts = lambda t: time.strftime("%m-%d %H:%M", time.gmtime(t + 7 * 3600))   # Asia/Ho_Chi_Minh


def spark(points: list[float], w=640, h=120) -> str:
    if len(points) < 2:
        return "<p class=muted>not enough equity points yet</p>"
    lo, hi = min(points), max(points)
    span = hi - lo or 1
    xy = " ".join(f"{i * w / (len(points) - 1):.1f},{h - (p - lo) / span * h:.1f}" for i, p in enumerate(points))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}"><polyline fill="none" stroke="#3b82f6" '
            f'stroke-width="2" points="{xy}"/></svg><p class=muted>min {lo:.2f} · max {hi:.2f}</p>')


def table(rows: list[list], head: list[str]) -> str:
    if not rows:
        return "<p class=muted>none</p>"
    return ("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>" +
            "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>")


def section(path: str) -> str:
    st, s = Store(path), stats(path)
    eq = st.all("equity")
    last = eq[-1] if eq else {}
    calls = st.all("llm_call")
    pos = last.get("positions") or {}
    trades = [["open", ts(t["ts"]), t["symbol"], t["side"], t["qty"], t["price"], t["sl"], t["tp"], ""]
              for t in st.all("trade_open")] + \
             [["close", ts(t["ts"]), t["symbol"], t["side"], t["qty"], round(t["exit"], 4), "", "", f"{t['pnl']:+.2f} ({t['why']})"]
              for t in st.all("trade_close")]
    trades.sort(key=lambda r: r[1], reverse=True)
    decisions = [[ts(d["ts"]), d["symbol"].split("/")[0], d["action"], d["confidence"],
                  "yes" if d["accepted"] else d["reject"] or "", d["reason"]] for d in st.all("decision")[-30:]][::-1]
    err = next((c for c in reversed(calls) if "error" in c), None)
    state = "🛑 HALTED (needs --clear-halt)" if halted(st) else "running"
    return f"""<section><h2>{e(os.path.basename(path))} · {e(s['model'])}</h2>
<div class=kpis><div><b>{s['equity'] or 0:.2f}</b><span>equity USDT</span></div>
<div><b>{e(state)}</b><span>{e(ts(last['ts'])) if last else '-'} last cycle</span></div>
<div><b>{s['trades']}</b><span>closed trades · win {s['win_rate']:.0%}</span></div>
<div><b>{s['net_pnl']:+.2f}</b><span>net PnL (after fees + LLM)</span></div>
<div><b>{s['max_dd']:.1%}</b><span>max drawdown</span></div>
<div><b>${s['llm_cost']:.3f}</b><span>LLM cost · {len(calls)} calls · {s['llm_errors']} errors</span></div></div>
{f"<p class=warn>last LLM error: {e(err['error'])}</p>" if err else ""}
<h3>Equity</h3>{spark([p['equity'] for p in eq[-500:]])}
<h3>Open positions</h3>{table([[k, v['side'], v['qty'], v['entry']] for k, v in pos.items()], ['symbol', 'side', 'qty', 'entry'])}
<h3>Trades</h3>{table(trades[:30], ['', 'time', 'symbol', 'side', 'qty', 'price', 'SL', 'TP', 'PnL'])}
<h3>LLM decisions (last 30)</h3>{table(decisions, ['time', 'sym', 'action', 'conf', 'accepted', 'reason'])}
</section>"""


def page() -> str:
    paths = [p for p in os.getenv("DASH_DBS", "").split(",") if p] or sorted(glob.glob("/data/*.db"))
    body = "".join(section(p) for p in paths if os.path.exists(p)) or "<p>no bot database yet</p>"
    return f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=60><title>trading-bot</title>
<style>body{{font:14px system-ui;margin:24px;background:#0b1220;color:#e5e7eb}}section{{margin-bottom:40px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}
.kpis div{{background:#111a2e;padding:12px;border-radius:8px}}.kpis b{{display:block;font-size:20px}}
.kpis span,.muted{{color:#94a3b8;font-size:12px}}.warn{{color:#fbbf24}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #1f2a44;padding:4px 8px;text-align:left;vertical-align:top}}
th{{color:#94a3b8;font-weight:500}}.out{{float:right}}.out button{{font:inherit;background:#1f2a44;color:#e5e7eb;border:0;padding:6px 12px;border-radius:6px;cursor:pointer}}</style>
<form class=out method=post action=/logout><button>Sign out</button></form><h1>trading-bot</h1><p class=muted>times UTC+7 · refreshes every 60 s</p>{body}"""


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
    return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>trading-bot · login</title><style>body{{font:15px system-ui;background:#0b1220;color:#e5e7eb;display:grid;place-items:center;min-height:100vh;margin:0}}
form{{background:#111a2e;padding:28px;border-radius:12px;width:min(320px,88vw);display:grid;gap:12px}}
h1{{margin:0 0 4px;font-size:20px}}label{{display:grid;gap:4px;font-size:13px;color:#94a3b8}}
input{{font:inherit;padding:10px;border-radius:8px;border:1px solid #1f2a44;background:#0b1220;color:#e5e7eb}}
button{{font:inherit;padding:10px;border:0;border-radius:8px;background:#3b82f6;color:#fff;cursor:pointer}}
.err{{color:#f87171;margin:0;font-size:13px}}</style>
<form method=post action=/login><h1>trading-bot</h1>{msg}
<label>User<input name=user autocomplete=username required autofocus></label>
<label>Password<input name=password type=password autocomplete=current-password required></label>
<button type=submit>Sign in</button></form>"""


CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str = "", headers: dict | None = None):
        out = body.encode()
        self.send_response(code)
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

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":   # public liveness probe, no data
            return self._send(200, "ok")
        if path == "/login":
            return self._send(200, login_page())
        if path != "/":
            return self._send(404, "not found")
        if not session_ok(self.headers.get("Cookie")):
            return self._send(303, "", {"Location": "/login"})
        self._send(200, page())

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
        self._send(401, login_page("Wrong user or password"))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(os.getenv("DASH_PASSWORD", "")) < 16:
        raise SystemExit("DASH_PASSWORD must be set (16+ chars)")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
