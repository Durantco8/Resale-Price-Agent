"""Email notification sender — retry-safe, injectable for testing.

Pattern reused from the seat tracker project: injectable send_fn,
per-notification try/except so one failure never blocks others.
"""

import json
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_TO = os.environ.get("NOTIFY_TO", "")


def send_email(to: str, subject: str, body: str) -> None:
    """Send an email via SMTP. Raises on failure."""
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def _format_price_drop_email(item_query: str, decision: dict) -> tuple[str, str]:
    """Build subject and body for a price_drop_alert notification."""
    signals = json.loads(decision.get("computed_signals") or "{}")
    price = signals.get("listing_price", "?")
    title = signals.get("title", item_query)
    item_url = signals.get("item_url", "")
    reasoning = decision.get("reasoning", "")

    subject = f"Price drop alert: {item_query}"

    lines = [
        f"Item: {title}",
        f"Search: {item_query}",
        f"Price: ${price}",
        "",
        f"Why: {reasoning}",
    ]

    if signals.get("target_price"):
        lines.append(f"Your target price: ${signals['target_price']}")
    if signals.get("rolling_avg"):
        lines.append(f"Rolling average: ${signals['rolling_avg']}")
    if item_url:
        lines.append(f"\nListing: {item_url}")

    return subject, "\n".join(lines)


def _format_buy_now_email(item_query: str, decision: dict) -> tuple[str, str]:
    """Build subject and body for an LLM buy_now notification."""
    signals = json.loads(decision.get("computed_signals") or "{}")
    confidence = decision.get("confidence", "?")
    reasoning = decision.get("reasoning", "")

    subject = f"Buy now recommendation: {item_query}"

    lines = [
        f"Search: {item_query}",
        f"Action: buy_now (confidence: {confidence})",
        "",
        f"Reasoning: {reasoning}",
        "",
        "Trend signals:",
    ]

    for key in ("avg_price", "min_price", "max_price", "price_trend",
                "price_trend_pct", "listing_trend", "listing_trend_pct"):
        if key in signals:
            label = key.replace("_", " ").title()
            lines.append(f"  {label}: {signals[key]}")

    return subject, "\n".join(lines)


def notify(
    item_query: str,
    decision: dict,
    send_fn=send_email,
    recipient: str | None = None,
) -> bool:
    """Send a notification if the decision warrants one.

    Returns True if an email was sent, False if skipped or failed.
    """
    event_type = decision.get("event_type", "")
    action = decision.get("action")

    # Decide whether this decision is notification-worthy
    if event_type == "price_drop_alert":
        subject, body = _format_price_drop_email(item_query, decision)
    elif event_type == "llm_reasoning" and action == "buy_now":
        subject, body = _format_buy_now_email(item_query, decision)
    else:
        return False

    to = recipient or NOTIFY_TO
    if not to:
        log.warning("No recipient configured — skipping notification.")
        return False

    try:
        send_fn(to, subject, body)
        log.info("Notification sent: %s", subject)
        return True
    except Exception:
        log.exception("Notification failed: %s", subject)
        return False
