from __future__ import annotations

"""
TrumpSignal uAgent — 注册到 AgentVerse / ASI:One，
让其他量化 Agent 可以通过 Agent Chat Protocol 发现并调用。
"""

import asyncio
import logging
from datetime import datetime, timezone

from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from config import settings
from pipeline.signal_store import signal_store

logger = logging.getLogger(__name__)

# ── 消息模型 ──────────────────────────────────────────────────────────────────


class SignalQueryRequest(Model):
    hours: int = 1
    source: str = ""
    asset: str = ""
    event_type: str = ""
    limit: int = 10


class SignalQueryResponse(Model):
    count: int
    signals: list[dict]
    disclaimer: str = (
        "Signals are for informational purposes only and do not constitute investment advice."
    )


# ── 协议 ──────────────────────────────────────────────────────────────────────

signal_protocol = Protocol(name="TrumpSignalProtocol", version="1.0")


@signal_protocol.on_message(model=SignalQueryRequest, replies=SignalQueryResponse)
async def handle_query(ctx: Context, sender: str, msg: SignalQueryRequest):
    ctx.logger.info("Query from %s: hours=%s asset=%s", sender, msg.hours, msg.asset)

    hours = max(1, min(msg.hours, 24))
    limit = max(1, min(msg.limit, 50))

    SOURCE_MAP = {
        "trump": "Truth Social",
        "whitehouse": "White House",
        "white house": "White House",
        "fed": "Federal Reserve",
        "fomc": "Federal Reserve",
    }
    source = SOURCE_MAP.get(msg.source.lower().strip()) if msg.source else None

    signals = signal_store.recent(
        max_age_seconds=hours * 3600,
        source=source,
        asset=msg.asset or None,
        event_type=msg.event_type or None,
        limit=limit,
    )
    await ctx.send(
        sender,
        SignalQueryResponse(count=len(signals), signals=signals),
    )


# ── Chat Protocol（ASI:One 自然语言入口）────────────────────────────────────────

chat_proto = Protocol(spec=chat_protocol_spec)

SOURCE_KEYWORDS = {
    "trump": "Truth Social",
    "truth social": "Truth Social",
    "white house": "White House",
    "whitehouse": "White House",
    "executive order": "White House",
    "fed": "Federal Reserve",
    "federal reserve": "Federal Reserve",
    "fomc": "Federal Reserve",
    "powell": "Federal Reserve",
}

# 常见资产关键词（大写匹配）
ASSET_KEYWORDS = ["BTC", "ETH", "SPX", "USD", "GOLD", "OIL", "NASDAQ", "DXY"]


def _format_signals(signals: list[dict]) -> str:
    if not signals:
        return (
            "No matching market signals in the requested window. "
            "I track Trump (Truth Social), the White House, and the Federal Reserve — "
            "try asking about recent Fed or White House events.\n\n"
            "_Not investment advice._"
        )
    lines = [f"**{len(signals)} signal(s) found:**\n"]
    for s in signals:
        et = s.get("event_type", "event")
        src = s.get("source", "?")
        summary = s.get("summary", "")
        urgency = s.get("urgency", "")
        lines.append(f"**[{et}] {src}**" + (f" · _{urgency}_" if urgency else ""))
        lines.append(summary)
        impacts = s.get("impacts") or s.get("assets_affected") or []
        if impacts:
            parts = []
            for a in impacts[:4]:
                sym = a.get("symbol") or a.get("asset", "?")
                direction = a.get("direction", "")
                conf = a.get("confidence")
                tag = sym + (f"({direction})" if direction else "")
                if conf is not None:
                    tag += f" {int(float(conf)*100)}%"
                parts.append(tag)
            lines.append("Impact: " + ", ".join(parts))
        lines.append("")
    lines.append("_Signals are informational only and do not constitute investment advice._")
    return "\n".join(lines)


def _query_from_text(text: str) -> list[dict]:
    low = text.lower()
    source = None
    for kw, canonical in SOURCE_KEYWORDS.items():
        if kw in low:
            source = canonical
            break
    asset = None
    for a in ASSET_KEYWORDS:
        if a.lower() in low or a in text:
            asset = a
            break
    # 简单时间窗口：提到 today/24/day → 24h，否则默认 6h
    hours = 24 if any(w in low for w in ["today", "24", "day", "latest"]) else 6
    return signal_store.recent(
        max_age_seconds=hours * 3600,
        source=source,
        asset=asset,
        limit=5,
    )


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    text = msg.text() if hasattr(msg, "text") else ""
    ctx.logger.info("Chat from %s: %s", sender, text[:120])

    # 先回 ack
    await ctx.send(
        sender,
        ChatAcknowledgement(acknowledged_msg_id=msg.msg_id),
    )

    try:
        signals = _query_from_text(text or "")
        reply = _format_signals(signals)
    except Exception as exc:  # 兜底，避免聊天直接挂掉
        ctx.logger.error("chat query failed: %s", exc)
        reply = "Sorry, I hit an error fetching signals. Please try again shortly."

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            content=[TextContent(type="text", text=reply)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("Chat ack from %s for %s", sender, msg.acknowledged_msg_id)


# ── Agent 初始化 ──────────────────────────────────────────────────────────────

agent = Agent(
    name="TrumpSignal",
    port=settings.agent_port,
    seed=settings.agent_seed_phrase,
    endpoint=[f"{settings.public_base_url}/submit"] if settings.public_base_url else [f"http://localhost:{settings.agent_port}/submit"],
)

agent.include(signal_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        "TrumpSignal Agent started. Address: %s\n"
        "Register this address on AgentVerse with keywords: "
        "event signals, political catalyst, Fed alerts, Trump signal, macro event, crypto news signal",
        ctx.agent.address,
    )


def run_agent():
    agent.run()
