from trader import dashboard


def test_session_cookie_signed_and_expires(monkeypatch):
    monkeypatch.setenv("DASH_USER", "u")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    assert dashboard.credentials_ok("u", "p" * 16)
    assert not dashboard.credentials_ok("u", "wrong") and not dashboard.credentials_ok("x", "p" * 16)
    s = dashboard.make_session(now=1000)
    assert dashboard.session_ok(f"s={s}", now=1000)
    assert not dashboard.session_ok(f"s={s}", now=1000 + dashboard.SESSION_S + 1)   # expired
    exp, sig = s.split(".")
    assert not dashboard.session_ok(f"s={int(exp) + 999}.{sig}", now=1000)          # tampered expiry
    assert not dashboard.session_ok("s=garbage", now=1000) and not dashboard.session_ok(None)
    monkeypatch.setenv("DASH_PASSWORD", "q" * 16)                                   # password change logs out
    assert not dashboard.session_ok(f"s={s}", now=1000)
    monkeypatch.setenv("DASH_PASSWORD", "")
    assert not dashboard.credentials_ok("u", "")


def test_login_flow_over_http(monkeypatch):
    import threading, urllib.request, urllib.error, urllib.parse
    from http.server import ThreadingHTTPServer
    monkeypatch.setenv("DASH_USER", "u")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    monkeypatch.setenv("DASH_INSECURE_COOKIE", "1")
    monkeypatch.setenv("DASH_DBS", "/nonexistent.db")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a):
            return None
    op = urllib.request.build_opener(NoRedirect)

    def call(path, data=None, cookie=None, origin=None):
        req = urllib.request.Request(base + path, data=urllib.parse.urlencode(data).encode() if data else None)
        if cookie:
            req.add_header("Cookie", cookie)
        if origin:
            req.add_header("Origin", origin)
        try:
            r = op.open(req)
        except urllib.error.HTTPError as e:
            r = e
        return r.status if hasattr(r, "status") else r.code, r.headers, r.read()

    assert call("/health")[2] == b"ok"
    code, h, _ = call("/")
    assert code == 303 and h["Location"] == "/login"
    assert call("/login")[0] == 200
    assert call("/login", {"user": "u", "password": "bad"})[0] == 401
    assert call("/login", {"user": "u", "password": "p" * 16}, origin="https://evil.example")[0] == 403
    code, h, _ = call("/login", {"user": "u", "password": "p" * 16})
    assert code == 303 and "HttpOnly" in h["Set-Cookie"] and "SameSite=Strict" in h["Set-Cookie"]
    cookie = h["Set-Cookie"].split(";")[0]
    code, _, body = call("/", cookie=cookie)
    assert code == 200 and b"<html" in body
    code, h, _ = call("/logout", {"x": "1"}, cookie=cookie)
    assert code == 303 and "Max-Age=0" in h["Set-Cookie"]
    srv.shutdown()
