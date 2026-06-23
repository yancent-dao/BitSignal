from __future__ import annotations

import asyncio
import logging

from sources.base import RawEvent
from .analyzer import analyze_event
from .dedup import deduplicator
from .signal_store import signal_store

logger = logging.getLogger(__name__)

# webhook 推送回调（由 gateway/webhook.py 注入）
_push_callbacks: list = []


def register_push_callback(cb) -> None:
    _push_callbacks.append(cb)


async def process_event(event: RawEvent) -> dict | None:
    """
    端到端处理一条原始事件：去重 → LLM 分析 → 存储 → 触发推送。
    返回生成的 signal dict 或 None（重复/噪声）。
    """
    if not deduplicator.is_new(event.event_id):
        return None

    signal = await analyze_event(event)
    if signal is None:
        return None

    signal_store.add(signal)

    # 异步触发所有 webhook 推送，不阻塞当前流程
    if _push_callbacks:
        asyncio.ensure_future(_fire_push(signal))

    return signal


async def _fire_push(signal: dict) -> None:
    for cb in _push_callbacks:
        try:
            await cb(signal)
        except Exception as exc:
            logger.warning("Push callback error: %s", exc)
