"""Discord alerts via a channel webhook. Without DISCORD_WEBHOOK_URL the message only goes to stdout."""
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
    url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url.startswith("https://discord.com/api/webhooks/"):
        return
    try:
        httpx.post(url, json={"content": f"[{tag}] {text}"[:1900]}, timeout=10)
    except Exception as e:   # an alert failure must never stop trading logic
        log.warning("discord failed: %s", type(e).__name__)
