"""Read-only status page over the bot databases: python -m trader.dashboard  (port 8080, DASH_DBS=/data/live.db,...)

Public behind Caddy (trade.brandondev.online): HTTP Basic auth with DASH_USER / DASH_PASSWORD is mandatory.
"""
import base64
import glob
import hmac
import html
import os
import time
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
th{{color:#94a3b8;font-weight:500}}</style><h1>trading-bot</h1><p class=muted>times UTC+7 · refreshes every 60 s</p>{body}"""


def authorized(header: str | None) -> bool:
    user, pw = os.getenv("DASH_USER", ""), os.getenv("DASH_PASSWORD", "")
    if not (user and pw and header and header.startswith("Basic ")):
        return False
    try:
        given = base64.b64decode(header[6:], validate=True)
    except ValueError:
        return False
    return hmac.compare_digest(given, f"{user}:{pw}".encode())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not authorized(self.headers.get("Authorization")):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="trading-bot"')
            self.end_headers()
            return
        if self.path != "/":
            self.send_error(404)
            return
        out = page().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(os.getenv("DASH_PASSWORD", "")) < 16:
        raise SystemExit("DASH_PASSWORD must be set (16+ chars)")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
