"""Telegram alerts. Without TELEGRAM_BOT_TOKEN the message only goes to stdout."""
import logging
import os

import httpx

log = logging.getLogger("notify")


def send(text: str):
    tag = os.getenv("BOT_NAME", "bot")
    log.info(text)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat, "text": f"[{tag}] {text}"[:4000]}, timeout=10)
    except Exception as e:   # an alert failure must never stop trading logic
        log.warning("telegram failed: %s", type(e).__name__)
