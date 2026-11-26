"""Telegram alerts. Without TELEGRAM_BOT_TOKEN the message only goes to stdout."""
import logging
import os
import re

import httpx

log = logging.getLogger("notify")


def redact(text: str) -> str:
    """ccxt puts signed request URLs in some error messages; never forward a signature."""
    return re.sub(r"signature=[0-9a-fA-F]+", "signature=<redacted>", text)


def send(text: str):
    tag = os.getenv("BOT_NAME", "bot")
    text = redact(text)
    log.info(text)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat, "text": f"[{tag}] {text}"[:4000]}, timeout=10)
    except Exception as e:   # an alert failure must never stop trading logic
        log.warning("telegram failed: %s", type(e).__name__)
