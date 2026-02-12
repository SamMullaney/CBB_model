"""Tests for American odds ↔ implied probability conversions."""

import pytest
from cbb.pricing.implied_prob import american_to_decimal, american_to_implied


class TestAmericanToImplied:
    def test_favourite(self):
        # -150 → 150/250 = 0.60
        assert american_to_implied(-150) == pytest.approx(0.6, abs=1e-6)

    def test_underdog(self):
        # +130 → 100/230 ≈ 0.43478
        assert american_to_implied(130) == pytest.approx(0.43478, abs=1e-4)

    def test_standard_vig_line(self):
        # -110 → 110/210 ≈ 0.52381
        assert american_to_implied(-110) == pytest.approx(0.52381, abs=1e-4)

    def test_even_money(self):
        # +100 → 100/200 = 0.50
        assert american_to_implied(100) == pytest.approx(0.5)

    def test_heavy_favourite(self):
        # -500 → 500/600 ≈ 0.8333
        assert american_to_implied(-500) == pytest.approx(0.8333, abs=1e-3)

    def test_big_underdog(self):
        # +500 → 100/600 ≈ 0.1667
        assert american_to_implied(500) == pytest.approx(0.1667, abs=1e-3)

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            american_to_implied(0)


class TestAmericanToDecimal:
    def test_favourite(self):
        # -150 → 1 + 100/150 = 1.6667
        assert american_to_decimal(-150) == pytest.approx(1.6667, abs=1e-3)

    def test_underdog(self):
        # +130 → 1 + 130/100 = 2.30
        assert american_to_decimal(130) == pytest.approx(2.30, abs=1e-3)

    def test_even_money(self):
        # +100 → 2.00
        assert american_to_decimal(100) == pytest.approx(2.0)

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            american_to_decimal(0)
