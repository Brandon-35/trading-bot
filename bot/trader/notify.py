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
WHY = {"stop_loss": "chạm cắt lỗ", "take_profit": "chạm chốt lời", "close": "bot chủ động đóng", "llm_close": "AI chủ động đóng",
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


_fx = {"rate": None, "t": 0.0}


def vnd(usdt: float, sign: bool = True) -> str:
    """' (≈ +10.900 ₫)' at the Binance P2P rate (cached 1 h); empty when the rate is unavailable."""
    import time
    if time.time() - _fx["t"] > 3600:
        _fx["t"] = time.time()
        try:
            from .dashboard import api_fx   # lazy: dashboard imports sync, which imports this module
            _fx["rate"] = api_fx()["usdt_vnd"]
        except Exception:
            pass
    r = _fx["rate"]
    return f" (≈ {num(round(usdt * r / 100) * 100, 0, sign)} ₫)" if r else ""


def money(usdt: float, sign: bool = True) -> str:
    return f"{num(usdt, 2 if abs(usdt) >= 1 else 3, sign)} USDT{vnd(usdt, sign)}"


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


def opened(symbol, side, qty, entry, sl, tp, lev, risk_usdt, risk_pct, reason, tp_label="Chốt lời", tp_qty=None):
    long = side == "long"
    pct = lambda x: num((x - entry) / entry * 100, 1, sign=True) + "%"   # noqa: E731
    gain = (tp_qty if tp_qty is not None else qty) * abs(tp - entry)
    card(f"{'🟢 MỞ LONG' if long else '🔴 MỞ SHORT'} · {coin(symbol)}", [
        f"**Nếu chạm cắt lỗ:** lỗ {money(-risk_usdt)}",
        f"**Nếu chạm {tp_label.lower()}:** lãi {money(gain)}",
        f"Giá vào {price(entry)} · cắt lỗ {price(sl)} ({pct(sl)}) · {tp_label.lower()} {price(tp)} ({pct(tp)})",
        f"Khối lượng {num(qty, 4).rstrip('0').rstrip(',')} {coin(symbol)} ≈ {num(qty * entry)} USDT · {lev}x · "
        f"rủi ro {num(risk_pct * 100, 1)}% vốn",
    ], GREEN if long else RED, reason)


def closed(symbol, pnl, why, r=None, reason=""):
    win = pnl > 0
    lines = [f"**Lý do:** {WHY.get(why, why)}"] + ([f"Kết quả: {num(r, 2, sign=True)}R"] if r is not None else [])
    card(f"{'✅ LÃI' if win else '❌ LỖ'} {money(pnl)} · {coin(symbol)}", lines, GREEN if win else RED, reason)


def daily(pnl_24h: float, equity: float, open_coins: list, ai_cost: float):
    card(f"📊 24 giờ qua: {'lãi' if pnl_24h >= 0 else 'lỗ'} {money(pnl_24h)}", [
        f"**Vốn hiện tại:** {money(equity, sign=False)}",
        f"**Đang mở:** {', '.join(open_coins) or 'không có'}",
        f"Chi phí AI từ đầu: ${ai_cost:.3f}"], GREEN if pnl_24h >= 0 else RED)


def started(lines):
    card("▶️ Khởi động", lines, BLUE)
