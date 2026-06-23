from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

_TTL = 86400 * 7  # 信号保留 7 天


class SignalStore:
    """内存信号存储，同时写 NDJSON 日志文件持久化。"""

    def __init__(self):
        self._signals: dict[str, tuple[dict, float]] = {}  # event_id -> (signal, ts)
        self._lock = Lock()
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(exist_ok=True)
        self._log_path = log_dir / "signals.ndjson"

    def add(self, signal: dict[str, Any]) -> None:
        eid = signal["event_id"]
        now = time.time()
        with self._lock:
            self._signals[eid] = (signal, now)
        # 追加写日志
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(signal, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Failed to write signal log: %s", exc)
        logger.info("Signal stored: %s [%s] %s", eid, signal.get("event_type"), signal.get("summary", "")[:80])

    def get(self, event_id: str) -> dict | None:
        with self._lock:
            entry = self._signals.get(event_id)
            return entry[0] if entry else None

    def recent(
        self,
        max_age_seconds: int = 3600,
        source: str | None = None,
        asset: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        now = time.time()
        with self._lock:
            results = []
            for sig, ts in self._signals.values():
                if now - ts > max_age_seconds:
                    continue
                if source and sig.get("source", "").lower() != source.lower():
                    continue
                if event_type and sig.get("event_type") != event_type:
                    continue
                if asset:
                    symbols = [i.get("symbol", "") for i in sig.get("impacts", [])]
                    if asset.lower() not in [s.lower() for s in symbols]:
                        continue
                results.append(sig)
            results.sort(key=lambda s: s.get("detected_at", ""), reverse=True)
            return results[:limit]

    def all_recent(self, max_age_seconds: int = 3600) -> list[dict]:
        return self.recent(max_age_seconds=max_age_seconds)

    def evict_old(self) -> None:
        now = time.time()
        with self._lock:
            expired = [k for k, (_, ts) in self._signals.items() if now - ts > _TTL]
            for k in expired:
                del self._signals[k]


signal_store = SignalStore()
