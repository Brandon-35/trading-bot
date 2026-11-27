"""Discord alerts via a channel webhook, as colored embeds in Vietnamese. Without DISCORD_WEBHOOK_URL the message
only goes to stdout."""
import logging
import os
import re

import httpx

log = logging.getLogger("notify")

# BOT_NAME (compose service) -> who is talking, shown on every card
LABEL = {"live": "💰 Bot tiền thật", "paper-signal": "🧪 Thử nghiệm · Chỉ tín hiệu",
         "paper-committee": "🧪 Thử nghiệm · Hội đồng AI"}
GREEN, RED, YELLOW, GREY, BLUE = 0x0ECB81, 0xF6465D, 0xF0B90B, 0x848E9C, 0x3B82F6
WHY = {"stop_loss": "chạm cắt lỗ", "take_profit": "chạm chốt lời", "close": "bot chủ động đóng",
       "breakeven": "dời stop về hoà vốn", "trail": "trailing stop", "committee": "AI siết stop"}


def redact(text: str) -> str:
    """ccxt puts signed request URLs in some error messages; never forward a signature."""
    return re.sub(r"signature=[0-9a-fA-F]+", "signature=<redacted>", text)


def num(v: float, d: int = 2, sign: bool = False) -> str:
    """vi-VN style: 1.234,56 and a real minus sign."""
    s = f"{abs(v):,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("−" if v < 0 else "+" if sign and v > 0 else "") + s


def price(v: float) -> str:
    a = abs(v)
    return num(v, 2 if a >= 1000 else 4 if a >= 1 else 6)


def coin(symbol: str) -> str:
    return symbol.split("/")[0]


def card(title: str, lines=(), color: int = GREY, reason: str = ""):
    tag = os.getenv("BOT_NAME", "bot")
    desc = "\n".join(lines)
    if reason:
        desc += ("\n" if desc else "") + "> " + redact(reason).replace("\n", " ")[:600]
    log.info("%s | %s", title, desc.replace("\n", " | "))
    url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url.startswith("https://discord.com/api/webhooks/"):
        return
    embed = {"author": {"name": LABEL.get(tag, tag)}, "title": redact(title)[:250], "description": redact(desc)[:3500],
             "color": color}
    try:
        httpx.post(url, json={"embeds": [embed]}, timeout=10)
    except Exception as e:   # an alert failure must never stop trading logic
        log.warning("discord failed: %s", type(e).__name__)


def send(text: str):
    """Plain one-line alert (errors, guards): a grey card, orange-yellow when it is a warning."""
    text = redact(text)
    card(text[:250], color=YELLOW if text.startswith(("⚠️", "🛑")) else GREY)


def opened(symbol, side, qty, entry, sl, tp, lev, risk_usdt, risk_pct, reason, tp_label="Chốt lời"):
    long = side == "long"
    pct = lambda x: num((x - entry) / entry * 100, 1, sign=True) + "%"   # noqa: E731
    card(f"{'🟢 MỞ LONG' if long else '🔴 MỞ SHORT'} · {coin(symbol)}", [
        f"**Giá vào:** {price(entry)}",
        f"**Cắt lỗ:** {price(sl)} ({pct(sl)})",
        f"**{tp_label}:** {price(tp)} ({pct(tp)})",
        f"**Khối lượng:** {num(qty, 4).rstrip('0').rstrip(',')} {coin(symbol)} ≈ {num(qty * entry)} USDT · {lev}x",
        f"**Rủi ro:** {num(risk_usdt, 3)} USDT ({num(risk_pct * 100, 1)}% vốn)",
    ], GREEN if long else RED, reason)


def closed(symbol, pnl, why, r=None, reason=""):
    win = pnl > 0
    lines = [f"**Lãi/lỗ ròng:** {num(pnl, 3, sign=True)} USDT" + (f" ({num(r, 2, sign=True)}R)" if r is not None else ""),
             f"**Lý do:** {WHY.get(why, why)}"]
    card(f"{'✅ ĐÓNG LÃI' if win else '❌ ĐÓNG LỖ'} · {coin(symbol)}", lines, GREEN if win else RED, reason)


def started(lines):
    card("▶️ Khởi động", lines, BLUE)
