"""LLM decision layer — uses Gemini API with JSON schema for structured output."""

import json
import logging
import os
from dataclasses import dataclass

from google import genai
from google.genai import types

from resale_price_agent.db import insert_decision
from resale_price_agent.signals import TrendSignals

log = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """\
You are a resale market analyst. You are given price trend signals and a \
summary of current listings for a specific item on eBay. Your job is to \
decide whether now is a good time to buy, whether to wait for a better \
price, or whether to skip this item entirely.

Respond with a JSON object containing your decision. Base your reasoning \
on the signals provided — do not invent data. Be concise."""

DECISION_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "action": types.Schema(
            type=types.Type.STRING,
            enum=["buy_now", "wait", "skip"],
            description="Recommended action.",
        ),
        "confidence": types.Schema(
            type=types.Type.NUMBER,
            description="Confidence in the recommendation (0 to 1).",
        ),
        "reasoning": types.Schema(
            type=types.Type.STRING,
            description="Brief explanation of the decision.",
        ),
    },
    required=["action", "confidence", "reasoning"],
)


@dataclass(frozen=True)
class LLMDecision:
    action: str        # buy_now | wait | skip
    confidence: float  # 0-1
    reasoning: str
    skipped: bool      # True if LLM was not called (insufficient data, parse error, etc.)
    skip_reason: str | None


def _build_user_message(signals_dict: dict, listing_summary: str) -> str:
    return (
        f"## Trend signals\n```json\n{json.dumps(signals_dict, indent=2)}\n```\n\n"
        f"## Current listings summary\n{listing_summary}"
    )


def get_llm_decision(
    engine,
    tracked_item_id: int,
    signals: TrendSignals,
    listing_summary: str,
    client=None,
    model: str = MODEL,
) -> LLMDecision:
    """Ask the LLM for a buy/wait/skip decision and store it.

    If ``signals.sufficient_data`` is False, skips the LLM call entirely.
    """
    if not signals.sufficient_data:
        reason = (
            f"Insufficient data ({signals.snapshot_count} snapshots, "
            f"need at least 5) — skipping LLM reasoning"
        )
        log.info("  #%d: %s", tracked_item_id, reason)
        return LLMDecision(
            action="skip",
            confidence=0.0,
            reasoning=reason,
            skipped=True,
            skip_reason="insufficient_data",
        )

    if client is None:
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
        )

    signals_dict = signals.to_dict()

    try:
        response = client.models.generate_content(
            model=model,
            contents=_build_user_message(signals_dict, listing_summary),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=DECISION_SCHEMA,
                max_output_tokens=512,
            ),
        )
    except Exception:
        reason = "Gemini API call failed"
        log.exception("  #%d: %s", tracked_item_id, reason)
        return LLMDecision(
            action="skip",
            confidence=0.0,
            reasoning=reason,
            skipped=True,
            skip_reason="api_error",
        )

    # --- Parse the JSON response ---
    decision = _parse_response(response)
    if decision is None:
        reason = "Could not parse LLM response"
        log.warning("  #%d: %s — raw: %s", tracked_item_id, reason, getattr(response, 'text', ''))
        return LLMDecision(
            action="skip",
            confidence=0.0,
            reasoning=reason,
            skipped=True,
            skip_reason="parse_error",
        )

    # --- Store in DB ---
    insert_decision(
        engine,
        tracked_item_id,
        "llm_reasoning",
        computed_signals=json.dumps(signals_dict),
        action=decision.action,
        confidence=decision.confidence,
        reasoning=decision.reasoning,
    )
    log.info(
        "  #%d: LLM says %s (confidence %.2f)",
        tracked_item_id, decision.action, decision.confidence,
    )
    return decision


def _parse_response(response) -> LLMDecision | None:
    """Extract a valid LLMDecision from the Gemini JSON response."""
    try:
        text = response.text
        if not text:
            return None
        data = json.loads(text)

        action = data.get("action")
        confidence = data.get("confidence")
        reasoning = data.get("reasoning")

        if action not in ("buy_now", "wait", "skip"):
            return None
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            return None
        if not isinstance(reasoning, str) or not reasoning:
            return None

        return LLMDecision(
            action=action,
            confidence=float(confidence),
            reasoning=reasoning,
            skipped=False,
            skip_reason=None,
        )
    except Exception:
        return None
