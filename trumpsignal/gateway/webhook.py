from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from pipeline.processor import register_push_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# subscription_id -> {url, channel, created_at}
_subscriptions: dict[str, dict] = {}

ALLOWED_CHANNELS = {"trump", "whitehouse", "fed", "all"}
SOURCE_MAP = {
    "trump": ["Truth Social", "X"],
    "whitehouse": ["White House"],
    "fed": ["Federal Reserve"],
    "all": None,  # None = 所有信源
}


class SubscribeRequest(BaseModel):
    webhook_url: str
    channel: str = "all"  # trump | whitehouse | fed | all

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v not in ALLOWED_CHANNELS:
            raise ValueError(f"channel must be one of {ALLOWED_CHANNELS}")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("webhook_url must be a valid http/https URL")
        return v


@router.post("/")
async def subscribe(req: SubscribeRequest):
    """订阅某频道的信号推送，事件触发时 POST 到你的 webhook URL。"""
    import hashlib
    sub_id = hashlib.sha256(f"{req.webhook_url}:{req.channel}:{time.time()}".encode()).hexdigest()[:12]
    _subscriptions[sub_id] = {
        "subscription_id": sub_id,
        "webhook_url": req.webhook_url,
        "channel": req.channel,
        "created_at": time.time(),
    }
    logger.info("New subscription %s: channel=%s url=%s", sub_id, req.channel, req.webhook_url)
    return {"subscription_id": sub_id, "channel": req.channel, "status": "active"}


@router.delete("/{subscription_id}")
async def unsubscribe(subscription_id: str):
    """取消订阅。"""
    if subscription_id not in _subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    del _subscriptions[subscription_id]
    return {"status": "cancelled"}


@router.get("/")
async def list_subscriptions():
    return {"subscriptions": list(_subscriptions.values())}


async def _push_signal(signal: dict[str, Any]) -> None:
    """推送信号到所有匹配的订阅者。"""
    source = signal.get("source", "")
    async with httpx.AsyncClient(timeout=10) as client:
        for sub in list(_subscriptions.values()):
            channel = sub["channel"]
            allowed_sources = SOURCE_MAP.get(channel)
            if allowed_sources is not None and source not in allowed_sources:
                continue
            try:
                await client.post(sub["webhook_url"], json=signal)
                logger.debug("Pushed signal %s to %s", signal["event_id"], sub["webhook_url"])
            except Exception as exc:
                logger.warning("Webhook push failed to %s: %s", sub["webhook_url"], exc)


# 注册推送回调
register_push_callback(_push_signal)
