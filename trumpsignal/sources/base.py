from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator

from pydantic import BaseModel


class RawEvent(BaseModel):
    """归一化的原始事件，采集层输出，分析层输入。"""

    event_id: str          # sha256(source+content)[:16]
    fetched_at: datetime
    source: str            # "Truth Social" / "X" / "White House" / "Federal Reserve"
    actor: str             # "Donald Trump" / "White House" / "Federal Reserve"
    content: str           # 原文
    url: str
    published_at: datetime | None = None


def make_event_id(source: str, content: str) -> str:
    h = hashlib.sha256(f"{source}:{content}".encode()).hexdigest()
    return h[:16]


class BaseSource(ABC):
    name: str
    actor: str

    @abstractmethod
    async def fetch(self) -> list[RawEvent]:
        """拉取最新条目，返回归一化事件列表（内部已处理 HTTP 异常）。"""
        ...
