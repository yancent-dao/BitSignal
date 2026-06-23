from __future__ import annotations

"""
TrumpSignal 启动入口。

同时运行：
- FastAPI HTTP 网关（含 x402 支付中间件）
- 信源轮询调度器（APScheduler）
- uAgent（AgentVerse 注册）
"""

import asyncio
import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from sources.truth_social import TruthSocialSource
from sources.twitter import TwitterSource
from sources.whitehouse import WhiteHouseSource
from sources.fed import FedSource
from pipeline.processor import process_event

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SOURCES = [
    TruthSocialSource(),
    TwitterSource(),
    WhiteHouseSource(),
    FedSource(),
]


async def poll_sources() -> None:
    for source in SOURCES:
        try:
            events = await source.fetch()
            for event in events:
                signal = await process_event(event)
                if signal:
                    logger.info(
                        "✅ New signal: [%s] %s → %s",
                        signal["event_type"],
                        signal["source"],
                        signal.get("summary", "")[:100],
                    )
        except Exception as exc:
            logger.error("Error polling %s: %s", source.name, exc)


@asynccontextmanager
async def lifespan(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_sources, "interval", seconds=15, id="poll_sources")
    scheduler.start()
    logger.info("Scheduler started — polling sources every 15s")

    # 启动 uAgent（后台线程）
    try:
        from agent.uagent import run_agent
        agent_thread = threading.Thread(target=run_agent, daemon=True)
        agent_thread.start()
        logger.info("uAgent started in background thread")
    except Exception as exc:
        logger.warning("uAgent failed to start: %s", exc)

    yield

    scheduler.shutdown(wait=False)


def main() -> None:
    from gateway.app import create_app
    app = create_app(lifespan=lifespan)

    uvicorn.run(
        app,
        host=settings.gateway_host,
        port=settings.effective_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
