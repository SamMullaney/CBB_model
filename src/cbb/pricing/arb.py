"""Arbitrage detection for h2h (moneyline) markets.

Pure math over PriceRow dicts — no DB, no network.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cbb.db.repo import PriceRow
from cbb.pricing.implied_prob import american_to_decimal, american_to_implied


@dataclass(frozen=True, slots=True)
class BestLeg:
    """Best available odds for one side of a bet."""

    outcome: str
    bookmaker: str
    odds_american: int
    implied_prob: float


@dataclass(frozen=True, slots=True)
class ArbOpportunity:
    """A detected arbitrage across bookmakers."""

    external_game_id: str
    captured_at: datetime
    market: str                  # always "h2h" for now
    leg_a: BestLeg
    leg_b: BestLeg
    arb_percent: float           # positive means profit (e.g. 0.02 = 2 %)
    stakes: dict[str, float]     # outcome -> stake for a $100 total wager


def arb_fingerprint(opp: ArbOpportunity) -> str:
    """Deterministic hash for deduplication.

    Two arbs are "the same" if they share the same game, market,
    books, and odds on both sides.  captured_at is excluded so that
    the same arb across consecutive snapshots is only alerted once.
    """
    # Sort legs by outcome name for stable ordering
    legs = sorted([opp.leg_a, opp.leg_b], key=lambda l: l.outcome)
    raw = "|".join([
        opp.external_game_id,
        opp.market,
        legs[0].outcome, legs[0].bookmaker, str(legs[0].odds_american),
        legs[1].outcome, legs[1].bookmaker, str(legs[1].odds_american),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _best_odds_per_outcome(
    rows: list[PriceRow],
) -> dict[str, tuple[str, int]]:
    """Find the highest American odds for each outcome across books.

    Returns:
        {outcome_name: (bookmaker, best_american_odds)}
    """
    best: dict[str, tuple[str, int]] = {}
    for r in rows:
        odds = r["odds_american"]
        if odds is None:
            continue
        outcome = r["outcome"]
        if outcome not in best or odds > best[outcome][1]:
            best[outcome] = (r["bookmaker"], odds)
    return best


def find_h2h_arbs(
    price_rows: list[PriceRow],
    min_edge: float = 0.002,
) -> list[ArbOpportunity]:
    """Scan h2h prices for arbitrage opportunities.

    For each game, finds the best moneyline odds per side across all
    bookmakers.  If the sum of implied probabilities < 1, an arb exists.

    Args:
        price_rows: Full snapshot (all markets). Non-h2h rows are filtered out.
        min_edge: Minimum arb margin to report (default 0.2 %).

    Returns:
        List of ArbOpportunity, sorted by arb_percent descending.
    """
    # Group h2h rows by game
    by_game: dict[str, list[PriceRow]] = defaultdict(list)
    for r in price_rows:
        if r["market"] == "h2h" and r["odds_american"] is not None:
            by_game[r["external_game_id"]].append(r)

    arbs: list[ArbOpportunity] = []

    for game_id, rows in by_game.items():
        best = _best_odds_per_outcome(rows)

        # h2h must have exactly 2 outcomes
        if len(best) != 2:
            continue

        outcomes = list(best.keys())
        book_a, odds_a = best[outcomes[0]]
        book_b, odds_b = best[outcomes[1]]

        prob_a = american_to_implied(odds_a)
        prob_b = american_to_implied(odds_b)
        total_implied = prob_a + prob_b
        arb_pct = 1.0 - total_implied

        if arb_pct < min_edge:
            continue

        # Stake split: guarantee equal payout on either side
        # stake_i = total * (implied_i / total_implied)
        total_stake = 100.0
        stake_a = round(total_stake * prob_a / total_implied, 2)
        stake_b = round(total_stake * prob_b / total_implied, 2)

        arbs.append(ArbOpportunity(
            external_game_id=game_id,
            captured_at=rows[0]["captured_at"],
            market="h2h",
            leg_a=BestLeg(
                outcome=outcomes[0],
                bookmaker=book_a,
                odds_american=odds_a,
                implied_prob=round(prob_a, 6),
            ),
            leg_b=BestLeg(
                outcome=outcomes[1],
                bookmaker=book_b,
                odds_american=odds_b,
                implied_prob=round(prob_b, 6),
            ),
            arb_percent=round(arb_pct, 6),
            stakes={outcomes[0]: stake_a, outcomes[1]: stake_b},
        ))

    arbs.sort(key=lambda a: a.arb_percent, reverse=True)
    return arbs
