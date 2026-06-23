from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import settings
from .base import BaseSource, RawEvent, make_event_id

logger = logging.getLogger(__name__)

TWITTERAPI_TIMELINE = "https://api.twitterapi.io/twitter/user/last_tweets"
TRUMP_USER_ID = "25073877"  # @realDonaldTrump


class TwitterSource(BaseSource):
    name = "X"
    actor = "Donald Trump"

    async def fetch(self) -> list[RawEvent]:
        if not settings.twitterapi_io_key:
            logger.debug("TWITTERAPI_IO_KEY not set, skipping X source")
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    TWITTERAPI_TIMELINE,
                    params={"userId": TRUMP_USER_ID, "count": 20},
                    headers={"X-API-Key": settings.twitterapi_io_key},
                )
                resp.raise_for_status()
            data = resp.json()
            tweets = data.get("tweets", []) or data.get("data", [])
            events = []
            for tw in tweets:
                text = tw.get("text", "") or tw.get("full_text", "")
                if not text:
                    continue
                created = tw.get("created_at")
                pub = None
                if created:
                    try:
                        pub = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y")
                    except Exception:
                        pass
                events.append(
                    RawEvent(
                        event_id=make_event_id(self.name, text),
                        fetched_at=datetime.now(timezone.utc),
                        source=self.name,
                        actor=self.actor,
                        content=text,
                        url=f"https://x.com/realDonaldTrump/status/{tw.get('id', '')}",
                        published_at=pub,
                    )
                )
            return events
        except Exception as exc:
            logger.warning("Twitter fetch failed: %s", exc)
            return []
