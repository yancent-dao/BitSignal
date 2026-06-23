from __future__ import annotations

from fastapi import APIRouter, Query

from pipeline.signal_store import signal_store

router = APIRouter(prefix="/signals", tags=["signals"])

SOURCE_ALIASES = {
    "trump": "Truth Social",
    "truth social": "Truth Social",
    "x": "X",
    "twitter": "X",
    "whitehouse": "White House",
    "white house": "White House",
    "fed": "Federal Reserve",
    "fomc": "Federal Reserve",
    "federal reserve": "Federal Reserve",
}


@router.get("/recent")
async def get_recent_signals(
    hours: int = Query(1, ge=1, le=24, description="最近 N 小时"),
    source: str | None = Query(None, description="信源过滤: trump / whitehouse / fed"),
    asset: str | None = Query(None, description="资产过滤: BTC / USD / auto_sector 等"),
    event_type: str | None = Query(None, description="事件类型: tariff_threat / monetary_policy 等"),
    limit: int = Query(20, ge=1, le=100),
):
    """查询最近 N 小时内的市场信号（付费接口，$0.01 USDC）。"""
    normalized_source = SOURCE_ALIASES.get(source.lower(), source) if source else None
    signals = signal_store.recent(
        max_age_seconds=hours * 3600,
        source=normalized_source,
        asset=asset,
        event_type=event_type,
        limit=limit,
    )
    return {"count": len(signals), "signals": signals}


@router.get("/{event_id}")
async def get_signal_by_id(event_id: str):
    """按 event_id 查询单条信号（付费接口，$0.01 USDC）。"""
    sig = signal_store.get(event_id)
    if sig is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Signal not found")
    return sig
