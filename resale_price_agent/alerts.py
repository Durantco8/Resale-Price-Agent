"""Alert matching and notification sending.

Given fresh polling data for a tracked item, determine which active
alerts should fire and send an email for each.  The email sender is
injectable (``send_fn``) so tests run with zero network calls.

Alerts are **ongoing** — they stay active until the user clicks the
one-click unsubscribe link included in every email.
"""

import logging

from resale_price_agent.db import get_active_alerts_for_item
from resale_price_agent.llm_reasoning import LLMDecision

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Condition parsing + matching
# ---------------------------------------------------------------------------

def _parse_price_below(condition: str) -> float | None:
    """Extract the threshold from a 'price_below:180.00' condition string."""
    if not condition.startswith("price_below:"):
        return None
    try:
        return float(condition.split(":", 1)[1])
    except (ValueError, IndexError):
        return None


def match_alerts(
    alerts: list[dict],
    new_snapshots: list[dict],
    llm_decision: LLMDecision | None,
) -> list[tuple[dict, str]]:
    """Return ``(alert, reason)`` pairs for alerts whose conditions are met.

    Pure logic — no DB access, no I/O.
    """
    matched: list[tuple[dict, str]] = []

    for alert in alerts:
        condition = alert.get("condition", "")

        # --- price_below:X ---
        threshold = _parse_price_below(condition)
        if threshold is not None:
            for snap in new_snapshots:
                if snap["price"] <= threshold:
                    reason = (
                        f"${snap['price']:.2f} is at or below your "
                        f"alert threshold of ${threshold:.2f}"
                    )
                    matched.append((alert, reason))
                    break  # one match per alert is enough
            continue

        # --- buy_now ---
        if condition == "buy_now":
            if (
                llm_decision is not None
                and not llm_decision.skipped
                and llm_decision.action == "buy_now"
            ):
                reason = (
                    f"Buy now recommendation "
                    f"(confidence: {llm_decision.confidence:.0%}): "
                    f"{llm_decision.reasoning}"
                )
                matched.append((alert, reason))
            continue

        # --- Unknown condition — skip gracefully ---
        log.warning(
            "Alert #%d has unrecognized condition %r — skipping.",
            alert.get("id", "?"), condition,
        )

    return matched


# ---------------------------------------------------------------------------
# Email formatting + sending
# ---------------------------------------------------------------------------

def _format_alert_email(
    alert: dict,
    tracked_item: dict,
    reason: str,
    unsubscribe_base_url: str = "",
) -> tuple[str, str]:
    """Build subject and body for an alert notification email."""
    display = tracked_item.get("display_name") or tracked_item.get("search_query", "")
    subject = f"Resale alert: {display}"

    token = alert["unsubscribe_token"]
    unsub_url = f"{unsubscribe_base_url}/unsubscribe/{token}" if unsubscribe_base_url else ""

    lines = [
        f"Item: {display}",
        f"Condition: {alert['condition']}",
        "",
        reason,
        "",
        "---",
        f"Unsubscribe token: {token}",
    ]
    if unsub_url:
        lines.append(f"Unsubscribe: {unsub_url}")

    return subject, "\n".join(lines)


def send_alert_email(
    alert: dict,
    tracked_item: dict,
    reason: str,
    send_fn,
) -> bool:
    """Format and send one alert email.  Returns True on success."""
    subject, body = _format_alert_email(alert, tracked_item, reason)
    try:
        send_fn(alert["email"], subject, body)
        log.info(
            "Alert #%d sent to %s: %s",
            alert.get("id", "?"), alert["email"], subject,
        )
        return True
    except Exception:
        log.exception(
            "Alert #%d failed to send to %s",
            alert.get("id", "?"), alert["email"],
        )
        return False


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def process_alerts(
    engine,
    tracked_item: dict,
    new_snapshots: list[dict],
    llm_decision: LLMDecision | None,
    send_fn,
) -> int:
    """Check and send all matching alerts for a tracked item.

    Returns the number of emails successfully sent.
    """
    active_alerts = get_active_alerts_for_item(engine, tracked_item["id"])
    if not active_alerts:
        return 0

    matched = match_alerts(active_alerts, new_snapshots, llm_decision)
    if not matched:
        return 0

    sent = 0
    for alert, reason in matched:
        if send_alert_email(alert, tracked_item, reason, send_fn):
            sent += 1

    return sent
