from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser
import httpx

from .base import BaseSource, RawEvent, make_event_id

logger = logging.getLogger(__name__)

WH_RSS_URLS = [
    "https://www.whitehouse.gov/news/feed/",
    "https://www.whitehouse.gov/presidential-actions/feed/",
]


class WhiteHouseSource(BaseSource):
    name = "White House"
    actor = "White House"

    async def fetch(self) -> list[RawEvent]:
        events: list[RawEvent] = []
        seen: set[str] = set()
        for url in WH_RSS_URLS:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, follow_redirects=True)
                    resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                for entry in feed.entries:
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    content = f"{title}\n{summary}".strip()
                    if not content or content in seen:
                        continue
                    seen.add(content)
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    events.append(
                        RawEvent(
                            event_id=make_event_id(self.name, content),
                            fetched_at=datetime.now(timezone.utc),
                            source=self.name,
                            actor=self.actor,
                            content=content,
                            url=getattr(entry, "link", url),
                            published_at=pub,
                        )
                    )
            except Exception as exc:
                logger.warning("WhiteHouse fetch failed (%s): %s", url, exc)
        return events
