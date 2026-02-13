"""Tests for h2h + spread arbitrage detection — all synthetic data, no DB."""

from datetime import datetime, timezone

from cbb.db.repo import PriceRow
from cbb.pricing.arb import find_all_arbs, find_h2h_arbs, find_spread_arbs

NOW = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)


def _price(
    game: str,
    book: str,
    outcome: str,
    odds: int,
    market: str = "h2h",
    line: float | None = None,
) -> PriceRow:
    """Helper to build a synthetic PriceRow."""
    return PriceRow(
        external_game_id=game,
        captured_at=NOW,
        bookmaker=book,
        market=market,
        outcome=outcome,
        line=line,
        odds_american=odds,
        odds_decimal=None,
    )


# ── H2H tests ───────────────────────────────────────────────────────

class TestFindH2hArbs:
    def test_clear_arb_is_detected(self):
        """Two books disagree enough to create a 2-side arb."""
        rows = [
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_a", "UNC", -130),
            _price("g1", "book_b", "Duke", -130),
            _price("g1", "book_b", "UNC", 110),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1

        opp = arbs[0]
        assert opp.external_game_id == "g1"
        assert opp.market == "h2h"
        assert opp.arb_percent > 0.04
        assert abs(opp.stakes["Duke"] - opp.stakes["UNC"]) < 1.0

    def test_no_arb_when_vig_too_high(self):
        rows = [
            _price("g1", "book_a", "Duke", -110),
            _price("g1", "book_a", "UNC", -110),
        ]
        assert len(find_h2h_arbs(rows, min_edge=0.0)) == 0

    def test_min_edge_filters_small_arbs(self):
        rows = [
            _price("g1", "book_a", "Duke", 103),
            _price("g1", "book_a", "UNC", -100),
            _price("g1", "book_b", "Duke", -100),
            _price("g1", "book_b", "UNC", 103),
        ]
        assert len(find_h2h_arbs(rows, min_edge=0.002)) == 1
        assert len(find_h2h_arbs(rows, min_edge=0.05)) == 0

    def test_non_h2h_rows_ignored(self):
        rows = [
            _price("g1", "book_a", "Duke", 110, market="spreads", line=-3.5),
            _price("g1", "book_a", "UNC", 110, market="spreads", line=3.5),
        ]
        assert len(find_h2h_arbs(rows, min_edge=0.0)) == 0

    def test_multiple_games(self):
        rows = [
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_b", "UNC", 110),
            _price("g1", "book_a", "UNC", -130),
            _price("g1", "book_b", "Duke", -130),
            _price("g2", "book_a", "Kansas", -150),
            _price("g2", "book_a", "Baylor", 130),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "g1"

    def test_picks_best_odds_across_books(self):
        rows = [
            _price("g1", "book_a", "Duke", -120),
            _price("g1", "book_b", "Duke", 105),
            _price("g1", "book_c", "Duke", -110),
            _price("g1", "book_a", "UNC", 105),
            _price("g1", "book_b", "UNC", -120),
            _price("g1", "book_c", "UNC", -110),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        legs = {arbs[0].leg_a.outcome: arbs[0].leg_a, arbs[0].leg_b.outcome: arbs[0].leg_b}
        assert legs["Duke"].bookmaker == "book_b"
        assert legs["Duke"].odds_american == 105
        assert legs["UNC"].bookmaker == "book_a"
        assert legs["UNC"].odds_american == 105

    def test_empty_input(self):
        assert find_h2h_arbs([], min_edge=0.0) == []

    def test_stake_split_sums_to_100(self):
        rows = [
            _price("g1", "book_a", "Duke", 150),
            _price("g1", "book_b", "Duke", -200),
            _price("g1", "book_a", "UNC", -170),
            _price("g1", "book_b", "UNC", 150),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        if arbs:
            assert abs(sum(arbs[0].stakes.values()) - 100.0) < 0.02

    def test_h2h_legs_have_no_line(self):
        rows = [
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_b", "UNC", 110),
            _price("g1", "book_a", "UNC", -130),
            _price("g1", "book_b", "Duke", -130),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert arbs[0].leg_a.line is None
        assert arbs[0].leg_b.line is None


# ── Spread tests ─────────────────────────────────────────────────────

class TestFindSpreadArbs:
    def test_clear_spread_arb(self):
        """Same line (3.5), different books, odds create arb."""
        rows = [
            # Book A: Duke -3.5 at +105
            _price("g1", "book_a", "Duke", 105, market="spreads", line=-3.5),
            _price("g1", "book_a", "UNC", -125, market="spreads", line=3.5),
            # Book B: UNC +3.5 at +105
            _price("g1", "book_b", "Duke", -125, market="spreads", line=-3.5),
            _price("g1", "book_b", "UNC", 105, market="spreads", line=3.5),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1

        opp = arbs[0]
        assert opp.market == "spreads"
        assert opp.arb_percent > 0.02
        # Each leg should carry its line
        legs = {opp.leg_a.outcome: opp.leg_a, opp.leg_b.outcome: opp.leg_b}
        assert legs["Duke"].line == -3.5
        assert legs["UNC"].line == 3.5

    def test_no_arb_with_standard_vig(self):
        """Both sides at -110 on the same line — no arb."""
        rows = [
            _price("g1", "book_a", "Duke", -110, market="spreads", line=-3.5),
            _price("g1", "book_a", "UNC", -110, market="spreads", line=3.5),
        ]
        assert len(find_spread_arbs(rows, min_edge=0.0)) == 0

    def test_different_lines_are_separate_groups(self):
        """Lines of 3.5 and 4.5 should not be mixed — each checked independently."""
        rows = [
            # Line 3.5: arb
            _price("g1", "book_a", "Duke", 105, market="spreads", line=-3.5),
            _price("g1", "book_b", "UNC", 105, market="spreads", line=3.5),
            _price("g1", "book_a", "UNC", -125, market="spreads", line=3.5),
            _price("g1", "book_b", "Duke", -125, market="spreads", line=-3.5),
            # Line 4.5: no arb (standard vig)
            _price("g1", "book_c", "Duke", -110, market="spreads", line=-4.5),
            _price("g1", "book_c", "UNC", -110, market="spreads", line=4.5),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        # The arb should be on the 3.5 line
        legs = {arbs[0].leg_a.outcome: arbs[0].leg_a, arbs[0].leg_b.outcome: arbs[0].leg_b}
        assert abs(legs["Duke"].line) == 3.5

    def test_h2h_rows_ignored(self):
        """H2H rows should not appear in spread arb results."""
        rows = [
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_b", "UNC", 110),
        ]
        assert len(find_spread_arbs(rows, min_edge=0.0)) == 0

    def test_spread_stake_split_sums_to_100(self):
        rows = [
            _price("g1", "book_a", "Duke", 110, market="spreads", line=-5.5),
            _price("g1", "book_b", "UNC", 110, market="spreads", line=5.5),
            _price("g1", "book_a", "UNC", -130, market="spreads", line=5.5),
            _price("g1", "book_b", "Duke", -130, market="spreads", line=-5.5),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        if arbs:
            assert abs(sum(arbs[0].stakes.values()) - 100.0) < 0.02

    def test_empty_input(self):
        assert find_spread_arbs([], min_edge=0.0) == []


# ── Combined tests ───────────────────────────────────────────────────

class TestFindAllArbs:
    def test_finds_both_h2h_and_spread_arbs(self):
        rows = [
            # H2H arb
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_b", "UNC", 110),
            _price("g1", "book_a", "UNC", -130),
            _price("g1", "book_b", "Duke", -130),
            # Spread arb (same game, different market)
            _price("g1", "book_a", "Duke", 105, market="spreads", line=-3.5),
            _price("g1", "book_b", "UNC", 105, market="spreads", line=3.5),
            _price("g1", "book_a", "UNC", -125, market="spreads", line=3.5),
            _price("g1", "book_b", "Duke", -125, market="spreads", line=-3.5),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        assert len(arbs) == 2
        markets = {a.market for a in arbs}
        assert markets == {"h2h", "spreads"}

    def test_sorted_by_arb_percent_descending(self):
        rows = [
            # Small h2h arb
            _price("g1", "book_a", "Duke", 102),
            _price("g1", "book_b", "UNC", 102),
            _price("g1", "book_a", "UNC", -110),
            _price("g1", "book_b", "Duke", -110),
            # Bigger spread arb
            _price("g2", "book_a", "Kansas", 120, market="spreads", line=-7.0),
            _price("g2", "book_b", "Baylor", 120, market="spreads", line=7.0),
            _price("g2", "book_a", "Baylor", -140, market="spreads", line=7.0),
            _price("g2", "book_b", "Kansas", -140, market="spreads", line=-7.0),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        assert len(arbs) == 2
        assert arbs[0].arb_percent >= arbs[1].arb_percent
