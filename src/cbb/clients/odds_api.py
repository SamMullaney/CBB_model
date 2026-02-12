"""Client for The Odds API — fetch only, no DB code."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from cbb.config.settings import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0  # seconds


def _is_rate_limited(exc: BaseException) -> bool:
    """Return True when the server responds with 429 Too Many Requests."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


@retry(
    retry=retry_if_exception(_is_rate_limited),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def fetch_odds(
    sport: str = "basketball_ncaab",
    markets: str = "spreads,totals,h2h",
    regions: str = "us",
    odds_format: str = "american",
) -> list[dict[str, Any]]:
    """Fetch live odds from The Odds API.

    Args:
        sport: Sport key (default: NCAAB).
        markets: Comma-separated market types.
        regions: Comma-separated regions (us, us2, uk, eu, au).
        odds_format: 'american' or 'decimal'.

    Returns:
        List of event dicts as returned by the API.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses (after retries for 429).
        ValueError: If the API key is not configured.
    """
    if not settings.odds_api_key:
        raise ValueError("ODDS_API_KEY is not set — check your .env file.")

    url = f"{settings.odds_api_base_url}/sports/{sport}/odds/"
    params = {
        "apiKey": settings.odds_api_key,
        "markets": markets,
        "regions": regions,
        "oddsFormat": odds_format,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    logger.info("Odds API call — remaining=%s used=%s", remaining, used)

    return resp.json()
