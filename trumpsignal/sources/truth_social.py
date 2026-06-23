from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser
import httpx

from .base import BaseSource, RawEvent, make_event_id

logger = logging.getLogger(__name__)

# Trump 的 Truth Social 账号 RSS（公开，无需认证）
TRUTH_SOCIAL_RSS = "https://truthsocial.com/@realDonaldTrump.rss"

# 备用：第三方聚合（当官方 RSS 失效时）
FALLBACK_RSS = "https://rss.truthsocial.com/users/realDonaldTrump/statuses.rss"


class TruthSocialSource(BaseSource):
    name = "Truth Social"
    actor = "Donald Trump"

    async def fetch(self) -> list[RawEvent]:
        for url in [TRUTH_SOCIAL_RSS, FALLBACK_RSS]:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, follow_redirects=True)
                    resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                events = []
                for entry in feed.entries:
                    content = getattr(entry, "summary", "") or getattr(entry, "title", "")
                    if not content:
                        continue
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
                return events
            except Exception as exc:
                logger.warning("TruthSocial fetch failed (%s): %s", url, exc)
        return []
