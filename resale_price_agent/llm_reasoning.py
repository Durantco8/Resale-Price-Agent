"""LLM decision layer — uses Claude API tool use for structured output."""

import json
import logging
import os
from dataclasses import dataclass

import anthropic

from resale_price_agent.db import insert_decision
from resale_price_agent.signals import TrendSignals

log = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are a resale market analyst. You are given price trend signals and a \
summary of current listings for a specific item on eBay. Your job is to \
decide whether now is a good time to buy, whether to wait for a better \
price, or whether to skip this item entirely.

Use the record_decision tool to report your decision. Base your reasoning \
on the signals provided — do not invent data. Be concise."""

DECISION_TOOL = {
    "name": "record_decision",
    "description": "Record a buy/wait/skip decision for the tracked item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["buy_now", "wait", "skip"],
                "description": "Recommended action.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in the recommendation (0-1).",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the decision.",
            },
        },
        "required": ["action", "confidence", "reasoning"],
    },
}


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
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

    signals_dict = signals.to_dict()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[DECISION_TOOL],
            tool_choice={"type": "tool", "name": "record_decision"},
            messages=[
                {
                    "role": "user",
                    "content": _build_user_message(signals_dict, listing_summary),
                }
            ],
        )
    except Exception:
        reason = "Claude API call failed"
        log.exception("  #%d: %s", tracked_item_id, reason)
        return LLMDecision(
            action="skip",
            confidence=0.0,
            reasoning=reason,
            skipped=True,
            skip_reason="api_error",
        )

    # --- Parse the tool-use response ---
    decision = _parse_response(response)
    if decision is None:
        reason = "Could not parse LLM response"
        log.warning("  #%d: %s — raw: %s", tracked_item_id, reason, response)
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
    """Extract a valid LLMDecision from the Claude tool-use response."""
    try:
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_decision":
                inp = block.input
                action = inp.get("action")
                confidence = inp.get("confidence")
                reasoning = inp.get("reasoning")

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
    return None
