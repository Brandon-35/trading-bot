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
    monkeypatch.setattr(notify.httpx, "post", lambda url, **k: sent.append((url, k["json"]["embeds"][0])))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://evil.example/x")
    notify.send("hi")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/abc")
    monkeypatch.setenv("BOT_NAME", "live")
    notify.send("⚠️ err signature=deadbeef")
    assert len(sent) == 1 and sent[0][0] == "https://discord.com/api/webhooks/1/abc"
    e = sent[0][1]
    assert e["title"] == "⚠️ err signature=<redacted>" and e["author"]["name"] == "💰 Bot tiền thật" and e["color"] == notify.YELLOW


def test_trade_cards_read_in_vietnamese(monkeypatch):
    sent = []
    monkeypatch.setattr(notify.httpx, "post", lambda url, **k: sent.append(k["json"]["embeds"][0]))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/abc")
    monkeypatch.setitem(notify._fx, "t", 9e18)
    notify.opened("SOL/USDT:USDT", "long", 0.52, 72.94, 72.222, 74.377, 5, 0.373, 0.02, "xu hướng tăng")
    notify.closed("BNB/USDT:USDT", -0.3731, "stop_loss", -1.0)
    o, c = sent
    assert o["title"] == "🟢 MỞ LONG · SOL" and o["color"] == notify.GREEN
    monkeypatch.setitem(notify._fx, "rate", 26_000.0)
    monkeypatch.setitem(notify._fx, "t", 9e18)
    sent.clear()
    notify.opened("SOL/USDT:USDT", "long", 0.52, 72.94, 72.222, 74.377, 5, 0.373, 0.02, "xu hướng tăng")
    notify.closed("BNB/USDT:USDT", -0.3731, "stop_loss", -1.0)
    o, c = sent
    assert o["description"].startswith("**Nếu chạm cắt lỗ:** lỗ −0,373 USDT (≈ −9.700 ₫)")
    assert "**Nếu chạm chốt lời:** lãi +0,747 USDT (≈ +19.400 ₫)" in o["description"]
    assert "Khối lượng 0,52 SOL ≈ 37,93 USDT · 5x" in o["description"] and o["description"].endswith("> xu hướng tăng")
    assert c["title"] == "❌ LỖ −0,373 USDT (≈ −9.700 ₫) · BNB" and "chạm cắt lỗ" in c["description"]
    assert notify.num(1234567.891) == "1.234.567,89"
