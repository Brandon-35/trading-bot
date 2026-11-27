"""Crypto headlines from public RSS feeds, passed to the LLM as market context (data, not instructions)."""
import datetime
import email.utils
import logging
import time
import xml.etree.ElementTree as ET

import httpx

log = logging.getLogger("news")
FEEDS = {"cointelegraph": "https://cointelegraph.com/rss", "decrypt": "https://decrypt.co/feed",
         "theblock": "https://www.theblock.co/rss.xml"}


def parse(xml: str, source: str, now: float, max_age_h: float) -> list[dict]:
    out = []
    for item in ET.fromstring(xml).iter("item"):
        title, date = (item.findtext("title") or "").strip(), item.findtext("pubDate")
        try:
            d = email.utils.parsedate_to_datetime(date)
            if d.tzinfo is None:   # "-0000" parses as naive; RSS dates are UTC then
                d = d.replace(tzinfo=datetime.timezone.utc)
            age = (now - d.timestamp()) / 3600
        except (TypeError, ValueError):
            continue
        if title and 0 <= age <= max_age_h:
            out.append({"source": source, "age_h": round(age, 1), "title": " ".join(title.split())[:200]})
    return out


def headlines(limit: int = 20, max_age_h: float = 12) -> list[dict]:
    """Newest headlines across feeds; a feed that fails is skipped (news is optional context)."""
    items, now = [], time.time()
    for source, url in FEEDS.items():
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            items += parse(r.text, source, now, max_age_h)
        except Exception as e:
            log.warning("news %s failed: %s", source, type(e).__name__)
    return sorted(items, key=lambda i: i["age_h"])[:limit]


if __name__ == "__main__":
    for h in headlines():
        print(h)
