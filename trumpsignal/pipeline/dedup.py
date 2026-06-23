from __future__ import annotations

import time
from threading import Lock


class Deduplicator:
    """内存去重，TTL 24 小时，防止重复处理同一条原始事件。"""

    def __init__(self, ttl_seconds: int = 86400):
        self._seen: dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()

    def is_new(self, event_id: str) -> bool:
        """返回 True 表示首次见到该 event_id（并记录之）；False 表示重复。"""
        now = time.time()
        with self._lock:
            self._evict(now)
            if event_id in self._seen:
                return False
            self._seen[event_id] = now
            return True

    def _evict(self, now: float) -> None:
        expired = [k for k, t in self._seen.items() if now - t > self._ttl]
        for k in expired:
            del self._seen[k]


deduplicator = Deduplicator()
