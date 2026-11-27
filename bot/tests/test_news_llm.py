import email.utils
import time

import pytest

from trader import llm, notify
from trader.news import parse

NOW = time.time()


def rss(*items):
    body = "".join(f"<item><title>{t}</title><pubDate>{email.utils.formatdate(NOW - h * 3600)}</pubDate></item>"
                   for t, h in items)
    return f"<rss><channel>{body}</channel></rss>"


def test_news_keeps_recent_headlines_only():
    out = parse(rss(("BTC ETF approved", 1), ("Old news", 30)), "x", NOW, 12)
    assert [o["title"] for o in out] == ["BTC ETF approved"] and out[0]["age_h"] == 1.0


def test_pick_uses_first_available_key(monkeypatch):
    for env, *_ in llm.PROVIDERS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        llm.pick()
    monkeypatch.setenv("OPENROUTER_API_KEY", "k0")
    assert llm.pick()["url"] == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("ZAI_API_KEY", "k")
    assert llm.pick()["model"] == "glm-5.3-flash"
    monkeypatch.setenv("OPENAI_API_KEY", "k2")
    assert llm.pick()["model"] == "gpt-6-luna"


def test_discord_needs_a_real_webhook_url(monkeypatch):
    sent = []
    monkeypatch.setattr(notify.httpx, "post", lambda url, **k: sent.append((url, k["json"]["content"])))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://evil.example/x")
    notify.send("hi")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/abc")
    notify.send("err signature=deadbeef")
    assert sent == [("https://discord.com/api/webhooks/1/abc", "[bot] err signature=<redacted>")]
