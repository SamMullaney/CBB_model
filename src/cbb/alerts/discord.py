"""Discord webhook alerts — send only, no DB code."""

from __future__ import annotations

import logging

import httpx

from cbb.pricing.arb import ArbOpportunity

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def _format_leg(leg) -> str:
    """Format one leg: outcome, line (if spread), odds, book."""
    line_str = f" ({leg.line:+g})" if leg.line is not None else ""
    return f"  {leg.outcome + line_str:<35s}  {leg.odds_american:>+5d}  @ {leg.bookmaker}"


def format_arb_message(opp: ArbOpportunity) -> str:
    """Build a human-readable Discord message for one arb opportunity."""
    a, b = opp.leg_a, opp.leg_b
    return (
        f"**ARB FOUND** ({opp.arb_percent * 100:.2f}%)\n"
        f"```\n"
        f"Game:   {a.outcome} vs {b.outcome}\n"
        f"Market: {opp.market}\n"
        f"\n"
        f"{_format_leg(a)}\n"
        f"{_format_leg(b)}\n"
        f"\n"
        f"Stake split ($100):\n"
        f"  {a.outcome}: ${opp.stakes[a.outcome]:.2f}\n"
        f"  {b.outcome}: ${opp.stakes[b.outcome]:.2f}\n"
        f"\n"
        f"Guaranteed profit: ${opp.arb_percent * 100:.2f}\n"
        f"```"
    )


def send_discord(webhook_url: str, message: str) -> None:
    """Post a message to a Discord webhook.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        ValueError: If webhook_url is empty.
    """
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL is not set.")

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(webhook_url, json={"content": message})
        resp.raise_for_status()

    logger.info("Discord alert sent (status %d)", resp.status_code)
