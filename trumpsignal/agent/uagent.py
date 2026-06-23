from __future__ import annotations

"""
TrumpSignal uAgent — 注册到 AgentVerse / ASI:One，
让其他量化 Agent 可以通过 Agent Chat Protocol 发现并调用。
"""

import asyncio
import logging

from uagents import Agent, Context, Model, Protocol

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


# ── Agent 初始化 ──────────────────────────────────────────────────────────────

agent = Agent(
    name="TrumpSignal",
    port=settings.agent_port,
    seed=settings.agent_seed_phrase,
    mailbox=True,
    network="testnet",
)

agent.include(signal_protocol, publish_manifest=True)


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
