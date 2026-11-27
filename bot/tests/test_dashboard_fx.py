import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from trader import dashboard


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    monkeypatch.setenv("DASH_INSECURE_COOKIE", "1")
    monkeypatch.setitem(dashboard._fx, "v", None)
    monkeypatch.setitem(dashboard._fx, "fail", 0.0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None


def get(base, path, auth=True):
    req = urllib.request.Request(base + path)
    if auth:
        req.add_header("Cookie", "s=" + dashboard.make_session())
    try:
        r = urllib.request.build_opener(NoRedirect).open(req)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def prices(monkeypatch, buy, sell, calls=None):
    def fake(t):
        if calls is not None:
            calls.append(t)
        return {"BUY": buy, "SELL": sell}[t]
    monkeypatch.setattr(dashboard, "_p2p_prices", fake)


def test_fx_needs_login(base):
    assert get(base, "/api/fx", auth=False)[0] == 401


def test_fx_median_mean_and_cache(base, monkeypatch):
    calls = []
    prices(monkeypatch, [26400, 26410, 26500], [26500, 26600, 26700, 26900], calls)   # medians 26410 / 26650
    code, body = get(base, "/api/fx")
    d = json.loads(body)
    assert code == 200 and d["buy"] == 26410 and d["sell"] == 26650 and d["usdt_vnd"] == 26530
    assert d["source"] == "Binance P2P" and d["stale"] is False and isinstance(d["time"], int)
    assert get(base, "/api/fx")[0] == 200 and len(calls) == 2   # second call served from cache


def test_fx_stale_on_failure_then_503_when_never_fetched(base, monkeypatch):
    monkeypatch.setattr(dashboard, "_p2p_prices", lambda t: (_ for _ in ()).throw(OSError("down")))
    assert get(base, "/api/fx")[0] == 503 and "error" in json.loads(get(base, "/api/fx")[1])
    prices(monkeypatch, [100.0], [110.0])
    dashboard._fx["fail"] = 0.0
    assert json.loads(get(base, "/api/fx")[1])["usdt_vnd"] == 105
    dashboard._fx["v"]["time"] -= 700   # cache expired
    monkeypatch.setattr(dashboard, "_p2p_prices", lambda t: (_ for _ in ()).throw(OSError("down")))
    d = json.loads(get(base, "/api/fx")[1])
    assert d["stale"] is True and d["usdt_vnd"] == 105


def test_report_needs_login(base):
    assert get(base, "/static/report.html", auth=False)[0] == 303
    code, body = get(base, "/static/report.html")
    assert code == 200 and b'class="rpt"' in body
