from trader import dashboard
from trader.store import Store


def test_page_renders_and_escapes_llm_text(tmp_path, monkeypatch):
    db = str(tmp_path / "live.db")
    st = Store(db)
    st.log("equity", equity=100.0, positions={"SOL/USDT:USDT": {"side": "long", "qty": 0.1, "entry": 140.0}})
    st.log("equity", equity=101.5, positions={})
    st.log("llm_call", model="m", cost=0.001)
    st.log("decision", symbol="SOL/USDT:USDT", action="long", confidence=0.7, accepted=False,
           reject="rr too low", reason="<script>alert(1)</script>")
    monkeypatch.setenv("DASH_DBS", db)
    html = dashboard.page()
    assert "101.50" in html and "rr too low" in html and "<polyline" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_auth_requires_exact_credentials(monkeypatch):
    import base64
    monkeypatch.setenv("DASH_USER", "u")
    monkeypatch.setenv("DASH_PASSWORD", "p" * 16)
    ok = "Basic " + base64.b64encode(b"u:" + b"p" * 16).decode()
    assert dashboard.authorized(ok)
    assert not dashboard.authorized(None)
    assert not dashboard.authorized("Basic " + base64.b64encode(b"u:wrong").decode())
    assert not dashboard.authorized("Basic !!!")
    monkeypatch.setenv("DASH_PASSWORD", "")
    assert not dashboard.authorized("Basic " + base64.b64encode(b"u:").decode())
