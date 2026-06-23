from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from config import settings
from sources.base import RawEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a quantitative finance event analyst specializing in political and macroeconomic signals.

Your task: given a raw post/statement from a high-influence source, determine if it has market significance and if so, produce a structured impact signal.

Covered assets (only map to these):
- US Equities sectors: auto_sector, energy_sector, tech_sector, banking_sector, healthcare_sector, defense_sector, retail_sector, agriculture_sector
- FX: USD (DXY)
- Crypto: BTC

Return a JSON object with this exact structure:
{
  "is_market_event": true/false,
  "event_type": "tariff_threat|monetary_policy|sanctions|regulation|personnel|geopolitical|earnings|other|noise",
  "summary": "1-2 sentence English summary of the event",
  "entities": ["list of mentioned entities, countries, sectors"],
  "impacts": [
    {
      "symbol": "asset symbol from covered list",
      "market": "US equities|FX|crypto",
      "direction": "bullish|bearish|neutral",
      "magnitude": "high|medium|low",
      "confidence": 0.0-1.0
    }
  ],
  "sentiment": "aggressive|moderate|cautious|neutral",
  "novelty": "high|medium|low",
  "urgency": "immediate|hours|days",
  "expected_time_to_impact": "<3min|<30min|<1h|hours|days",
  "rationale": "1-2 sentence explanation of why these assets are impacted"
}

If is_market_event is false, all other fields can be null/empty.
Return ONLY valid JSON, no markdown, no explanation."""


async def analyze_event(event: RawEvent) -> dict | None:
    """
    调用 OpenRouter LLM 分析原始事件，返回结构化信号 dict；
    若非市场事件返回 None。
    """
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return None

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )

    user_msg = (
        f"Source: {event.source}\n"
        f"Actor: {event.actor}\n"
        f"Published: {event.published_at or event.fetched_at}\n"
        f"Content:\n{event.content}"
    )

    try:
        resp = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip()
        # 去除 markdown 代码块包裹
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()
        if not raw:
            logger.warning("LLM returned empty content for event %s", event.event_id)
            return None
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON for event %s: %s", event.event_id, exc)
        return None
    except Exception as exc:
        logger.error("LLM call failed for event %s: %s", event.event_id, exc)
        return None

    if not data.get("is_market_event"):
        logger.debug("Event %s filtered as non-market noise", event.event_id)
        return None

    # 补充字段
    data["event_id"] = event.event_id
    data["detected_at"] = datetime.now(timezone.utc).isoformat()
    data["source"] = event.source
    data["actor"] = event.actor
    data["source_url"] = event.url
    data["published_at"] = (event.published_at or event.fetched_at).isoformat()
    data["disclaimer"] = (
        "This signal is for informational purposes only and does not constitute "
        "investment advice. Past signals do not guarantee future market movements."
    )
    return data
