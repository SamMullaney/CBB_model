"""Supported sports and markets for arb scanning.

Add or remove entries here to control which sports the bot fetches.
Keys must match The Odds API sport_key values.
"""

from __future__ import annotations

SPORTS: list[str] = [
    "basketball_ncaab",
    "basketball_nba",
    "americanfootball_nfl",
    "icehockey_nhl",
    "baseball_mlb",
]

# Markets to request from the Odds API (comma-separated for the API call)
MARKETS: list[str] = [
    "h2h",
    "spreads",
]

MARKETS_PARAM: str = ",".join(MARKETS)
