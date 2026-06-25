from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, Request, Response

from config import settings
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

from .routes_pull import router as pull_router
from .webhook import router as webhook_router  # noqa: F401 – registers push callback as side effect

_UAGENT_BASE = f"http://127.0.0.1:{settings.agent_port}"


def create_app(lifespan=None) -> FastAPI:
    app = FastAPI(
        title="TrumpSignal",
        description=(
            "Event-driven market impact signals from Trump, White House, and Federal Reserve. "
            "Powered by BitSignal · x402 USDC payments on Base."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def index() -> dict[str, Any]:
        return {
            "name": "TrumpSignal",
            "description": "Real-time event impact signals · $0.01 USDC per query",
            "endpoints": {
                "GET /signals/recent": "Query recent market signals (paid)",
                "GET /signals/{event_id}": "Get signal by ID (paid)",
                "POST /subscriptions": "Subscribe to webhook push (free to subscribe)",
                "DELETE /subscriptions/{id}": "Unsubscribe",
                "GET /log": "Public event log",
            },
            "payment": "x402 · USDC on Base · $0.01 per call",
            "disclaimer": "Signals are for informational purposes only. Not investment advice.",
        }

    @app.get("/log")
    async def public_log() -> dict[str, Any]:
        from pipeline.signal_store import signal_store
        recent = signal_store.recent(max_age_seconds=86400 * 7, limit=100)
        return {
            "count": len(recent),
            "signals": [
                {
                    "event_id": s["event_id"],
                    "detected_at": s["detected_at"],
                    "source": s["source"],
                    "actor": s["actor"],
                    "event_type": s.get("event_type"),
                    "summary": s.get("summary"),
                    "urgency": s.get("urgency"),
                }
                for s in recent
            ],
        }

    # ── ACP 代理路由：把 AgentVerse 发来的消息转发给本地 uAgent ─────────────────
    @app.api_route("/submit", methods=["POST", "HEAD"])
    async def acp_submit(request: Request) -> Response:
        body = await request.body()
        # Forward all headers so x-uagents-connection: sync is preserved
        forward_headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=f"{_UAGENT_BASE}/submit",
                content=body,
                headers=forward_headers,
                timeout=30.0,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )

    @app.get("/agent_info")
    async def acp_agent_info() -> Response:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_UAGENT_BASE}/agent_info", timeout=5.0)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )

    app.include_router(pull_router)
    app.include_router(webhook_router)

    # x402 支付中间件
    facilitator = HTTPFacilitatorClient(
        FacilitatorConfig(url="https://x402.org/facilitator")
    )
    server = x402ResourceServer(facilitator)
    server.register(settings.evm_network, ExactEvmServerScheme())

    _payment_option = PaymentOption(
        scheme="exact",
        pay_to=settings.payment_recipient_address,
        price=settings.signal_price,
        network=settings.evm_network,
    )

    routes: dict[str, RouteConfig] = {
        "GET /signals/recent": RouteConfig(
            accepts=[_payment_option],
            mime_type="application/json",
            description="Recent market impact signals",
        ),
        "GET /signals/{event_id}": RouteConfig(
            accepts=[_payment_option],
            mime_type="application/json",
            description="Single market impact signal by ID",
        ),
    }

    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

    return app
