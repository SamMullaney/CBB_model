"""Arbitrage detection for h2h and spreads markets.

Pure math over PriceRow dicts — no DB, no network.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from cbb.db.repo import PriceRow
from cbb.pricing.implied_prob import american_to_implied


@dataclass(frozen=True, slots=True)
class BestLeg:
    """Best available odds for one side of a bet."""

    outcome: str
    bookmaker: str
    odds_american: int
    implied_prob: float
    line: float | None = None  # spread number; None for h2h


@dataclass(frozen=True, slots=True)
class ArbOpportunity:
    """A detected arbitrage across bookmakers."""

    external_game_id: str
    captured_at: datetime
    market: str               # h2h | spreads
    leg_a: BestLeg
    leg_b: BestLeg
    arb_percent: float        # positive means profit (e.g. 0.02 = 2 %)
    stakes: dict[str, float]  # outcome label -> stake for a $100 total wager


def arb_fingerprint(opp: ArbOpportunity) -> str:
    """Deterministic hash for deduplication.

    Two arbs are "the same" if they share the same game, market,
    line, books, and odds on both sides.  captured_at is excluded
    so that the same arb across consecutive snapshots is only alerted once.
    """
    legs = sorted([opp.leg_a, opp.leg_b], key=lambda l: l.outcome)
    raw = "|".join([
        opp.external_game_id,
        opp.market,
        str(legs[0].line),
        legs[0].outcome, legs[0].bookmaker, str(legs[0].odds_american),
        str(legs[1].line),
        legs[1].outcome, legs[1].bookmaker, str(legs[1].odds_american),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Helpers ──────────────────────────────────────────────────────────

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


def _check_two_side_arb(
    best: dict[str, tuple[str, int]],
    game_id: str,
    captured_at: datetime,
    market: str,
    min_edge: float,
    lines: dict[str, float | None] | None = None,
) -> ArbOpportunity | None:
    """Check if the two best-priced outcomes form an arb.

    Args:
        best: {outcome: (bookmaker, odds_american)} — must have exactly 2 entries.
        game_id: External game ID.
        captured_at: Snapshot timestamp.
        market: "h2h" or "spreads".
        min_edge: Minimum arb margin.
        lines: {outcome: line} for spreads; None for h2h.
    """
    if len(best) != 2:
        return None

    outcomes = list(best.keys())
    book_a, odds_a = best[outcomes[0]]
    book_b, odds_b = best[outcomes[1]]

    prob_a = american_to_implied(odds_a)
    prob_b = american_to_implied(odds_b)
    total_implied = prob_a + prob_b
    arb_pct = 1.0 - total_implied

    if arb_pct < min_edge:
        return None

    total_stake = 100.0
    stake_a = round(total_stake * prob_a / total_implied, 2)
    stake_b = round(total_stake * prob_b / total_implied, 2)

    line_a = lines[outcomes[0]] if lines else None
    line_b = lines[outcomes[1]] if lines else None

    return ArbOpportunity(
        external_game_id=game_id,
        captured_at=captured_at,
        market=market,
        leg_a=BestLeg(
            outcome=outcomes[0],
            bookmaker=book_a,
            odds_american=odds_a,
            implied_prob=round(prob_a, 6),
            line=line_a,
        ),
        leg_b=BestLeg(
            outcome=outcomes[1],
            bookmaker=book_b,
            odds_american=odds_b,
            implied_prob=round(prob_b, 6),
            line=line_b,
        ),
        arb_percent=round(arb_pct, 6),
        stakes={outcomes[0]: stake_a, outcomes[1]: stake_b},
    )


# ── H2H arb detection ───────────────────────────────────────────────

def find_h2h_arbs(
    price_rows: list[PriceRow],
    min_edge: float = 0.002,
) -> list[ArbOpportunity]:
    """Scan h2h prices for arbitrage opportunities.

    For each game, finds the best moneyline odds per side across all
    bookmakers.  If the sum of implied probabilities < 1, an arb exists.
    """
    by_game: dict[str, list[PriceRow]] = defaultdict(list)
    for r in price_rows:
        if r["market"] == "h2h" and r["odds_american"] is not None:
            by_game[r["external_game_id"]].append(r)

    arbs: list[ArbOpportunity] = []
    for game_id, rows in by_game.items():
        best = _best_odds_per_outcome(rows)
        opp = _check_two_side_arb(best, game_id, rows[0]["captured_at"], "h2h", min_edge)
        if opp:
            arbs.append(opp)

    arbs.sort(key=lambda a: a.arb_percent, reverse=True)
    return arbs


# ── Spread arb detection ────────────────────────────────────────────

def find_spread_arbs(
    price_rows: list[PriceRow],
    min_edge: float = 0.002,
) -> list[ArbOpportunity]:
    """Scan spread prices for arbitrage opportunities.

    True spread arbs require the same absolute line at different books:
        Book A: Team -3.5 (-105)
        Book B: Opponent +3.5 (-105)

    Groups by (game_id, abs(line)), then finds best odds for each side.
    """
    # Group spread rows by (game_id, abs_line)
    by_group: dict[tuple[str, float], list[PriceRow]] = defaultdict(list)
    for r in price_rows:
        if r["market"] != "spreads" or r["odds_american"] is None or r["line"] is None:
            continue
        abs_line = round(abs(float(r["line"])), 1)
        by_group[(r["external_game_id"], abs_line)].append(r)

    arbs: list[ArbOpportunity] = []

    for (game_id, abs_line), rows in by_group.items():
        # Split into favorite side (negative line) and underdog side (positive line)
        # Use outcome name as key to find best odds per side
        best: dict[str, tuple[str, int]] = {}
        lines: dict[str, float] = {}

        for r in rows:
            outcome = r["outcome"]
            odds = r["odds_american"]
            if outcome not in best or odds > best[outcome][1]:
                best[outcome] = (r["bookmaker"], odds)
                lines[outcome] = float(r["line"])

        opp = _check_two_side_arb(
            best, game_id, rows[0]["captured_at"], "spreads", min_edge, lines
        )
        if opp:
            arbs.append(opp)

    arbs.sort(key=lambda a: a.arb_percent, reverse=True)
    return arbs


# ── Combined scanner ────────────────────────────────────────────────

def find_all_arbs(
    price_rows: list[PriceRow],
    min_edge: float = 0.002,
) -> list[ArbOpportunity]:
    """Find arbs across all supported markets (h2h + spreads).

    Returns combined list sorted by arb_percent descending.
    """
    arbs = find_h2h_arbs(price_rows, min_edge) + find_spread_arbs(price_rows, min_edge)
    arbs.sort(key=lambda a: a.arb_percent, reverse=True)
    return arbs
