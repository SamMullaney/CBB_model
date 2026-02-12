"""Tests for h2h arbitrage detection — all synthetic data, no DB."""

from datetime import datetime, timezone

from cbb.db.repo import PriceRow
from cbb.pricing.arb import find_h2h_arbs

NOW = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)


def _price(
    game: str,
    book: str,
    outcome: str,
    odds: int,
    market: str = "h2h",
) -> PriceRow:
    """Helper to build a synthetic PriceRow."""
    return PriceRow(
        external_game_id=game,
        captured_at=NOW,
        bookmaker=book,
        market=market,
        outcome=outcome,
        line=None,
        odds_american=odds,
        odds_decimal=None,
    )


class TestFindH2hArbs:
    def test_clear_arb_is_detected(self):
        """Two books disagree enough to create a 2-side arb."""
        rows = [
            # Book A has Duke as underdog at +110
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_a", "UNC", -130),
            # Book B has UNC as underdog at +110
            _price("g1", "book_b", "Duke", -130),
            _price("g1", "book_b", "UNC", 110),
        ]
        # Best Duke = +110 (book_a), best UNC = +110 (book_b)
        # implied: 100/210 + 100/210 = 0.4762 + 0.4762 = 0.9524
        # arb_pct = 1 - 0.9524 = 0.0476 (4.76 %)
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1

        opp = arbs[0]
        assert opp.external_game_id == "g1"
        assert opp.market == "h2h"
        assert opp.arb_percent > 0.04
        # Stakes should be roughly equal (symmetric odds)
        assert abs(opp.stakes["Duke"] - opp.stakes["UNC"]) < 1.0

    def test_no_arb_when_vig_too_high(self):
        """Standard vig lines — no arb."""
        rows = [
            _price("g1", "book_a", "Duke", -110),
            _price("g1", "book_a", "UNC", -110),
        ]
        # implied: 0.5238 + 0.5238 = 1.0476 → no arb
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 0

    def test_min_edge_filters_small_arbs(self):
        """Arb exists but below min_edge threshold."""
        rows = [
            _price("g1", "book_a", "Duke", 103),
            _price("g1", "book_a", "UNC", -100),
            _price("g1", "book_b", "Duke", -100),
            _price("g1", "book_b", "UNC", 103),
        ]
        # Best Duke = +103 → 100/203 = 0.4926
        # Best UNC  = +103 → 100/203 = 0.4926
        # sum = 0.9852, arb = 0.0148 (1.48 %)
        # Should pass with default min_edge=0.002
        assert len(find_h2h_arbs(rows, min_edge=0.002)) == 1
        # Should be filtered at 5 % threshold
        assert len(find_h2h_arbs(rows, min_edge=0.05)) == 0

    def test_non_h2h_rows_ignored(self):
        """Spreads rows should not affect h2h arb detection."""
        rows = [
            _price("g1", "book_a", "Duke", 110, market="spreads"),
            _price("g1", "book_a", "UNC", 110, market="spreads"),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 0

    def test_multiple_games(self):
        """Arb in one game, not in the other."""
        rows = [
            # Game 1: arb
            _price("g1", "book_a", "Duke", 110),
            _price("g1", "book_b", "UNC", 110),
            _price("g1", "book_a", "UNC", -130),
            _price("g1", "book_b", "Duke", -130),
            # Game 2: no arb
            _price("g2", "book_a", "Kansas", -150),
            _price("g2", "book_a", "Baylor", 130),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "g1"

    def test_picks_best_odds_across_books(self):
        """Should select the highest American odds per side."""
        rows = [
            _price("g1", "book_a", "Duke", -120),
            _price("g1", "book_b", "Duke", 105),   # better
            _price("g1", "book_c", "Duke", -110),
            _price("g1", "book_a", "UNC", 105),     # better
            _price("g1", "book_b", "UNC", -120),
            _price("g1", "book_c", "UNC", -110),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        opp = arbs[0]
        # Best Duke from book_b at +105, best UNC from book_a at +105
        legs = {opp.leg_a.outcome: opp.leg_a, opp.leg_b.outcome: opp.leg_b}
        assert legs["Duke"].bookmaker == "book_b"
        assert legs["Duke"].odds_american == 105
        assert legs["UNC"].bookmaker == "book_a"
        assert legs["UNC"].odds_american == 105

    def test_empty_input(self):
        assert find_h2h_arbs([], min_edge=0.0) == []

    def test_stake_split_sums_to_100(self):
        """Stakes for a $100 wager should sum to ~$100."""
        rows = [
            _price("g1", "book_a", "Duke", 150),
            _price("g1", "book_b", "Duke", -200),
            _price("g1", "book_a", "UNC", -170),
            _price("g1", "book_b", "UNC", 150),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        if arbs:
            total = sum(arbs[0].stakes.values())
            assert abs(total - 100.0) < 0.02
