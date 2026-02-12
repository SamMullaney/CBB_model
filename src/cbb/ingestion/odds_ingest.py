"""Flatten raw Odds API JSON into normalised row dicts.

No DB code, no network calls — pure transformation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cbb.db.repo import GameRow, PriceRow


@dataclass(frozen=True, slots=True)
class OddsRow:
    """One price point from one bookmaker for one outcome."""

    game_id: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    market: str          # h2h | spreads | totals
    outcome_name: str    # team name, "Over", or "Under"
    price: int           # american odds
    point: float | None  # spread / total line; None for h2h


def normalize_odds(events: list[dict[str, Any]]) -> list[OddsRow]:
    """Convert raw Odds API response into a flat list of OddsRows.

    Args:
        events: The JSON list returned by GET /v4/sports/{sport}/odds/.

    Returns:
        One OddsRow per outcome per market per bookmaker per event.
    """
    rows: list[OddsRow] = []

    for event in events:
        game_id = event["id"]
        commence_time = event["commence_time"]
        home_team = event["home_team"]
        away_team = event["away_team"]

        for book in event.get("bookmakers", []):
            bookmaker = book["key"]

            for market in book.get("markets", []):
                market_key = market["key"]

                for outcome in market.get("outcomes", []):
                    rows.append(
                        OddsRow(
                            game_id=game_id,
                            commence_time=commence_time,
                            home_team=home_team,
                            away_team=away_team,
                            bookmaker=bookmaker,
                            market=market_key,
                            outcome_name=outcome["name"],
                            price=outcome["price"],
                            point=outcome.get("point"),
                        )
                    )

    return rows


def _parse_iso(raw: str) -> datetime:
    """Parse ISO-8601 timestamp from the Odds API (always UTC)."""
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def prepare_for_db(
    rows: list[OddsRow],
    sport_key: str,
) -> tuple[list[GameRow], list[PriceRow]]:
    """Convert OddsRows into the shapes expected by insert_games_and_prices.

    Deduplicates games and stamps every price row with a single captured_at.
    """
    captured_at = datetime.now(timezone.utc)

    seen_games: dict[str, GameRow] = {}
    prices: list[PriceRow] = []

    for r in rows:
        if r.game_id not in seen_games:
            seen_games[r.game_id] = GameRow(
                external_game_id=r.game_id,
                sport_key=sport_key,
                commence_time=_parse_iso(r.commence_time),
                home_team=r.home_team,
                away_team=r.away_team,
            )

        prices.append(PriceRow(
            external_game_id=r.game_id,
            captured_at=captured_at,
            bookmaker=r.bookmaker,
            market=r.market,
            outcome=r.outcome_name,
            line=r.point,
            odds_american=r.price,
            odds_decimal=None,
        ))

    return list(seen_games.values()), prices
