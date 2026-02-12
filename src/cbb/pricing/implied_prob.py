"""American odds ↔ implied probability conversion.

Pure math — no DB, no network.
"""

from __future__ import annotations


def american_to_implied(odds: int) -> float:
    """Convert American odds to an implied probability in (0, 1).

    Examples:
        -150 → 0.6000   (favourite)
        +130 → 0.4348   (underdog)
        -110 → 0.5238   (standard vig line)

    Raises:
        ValueError: If odds is zero (not a valid American line).
    """
    if odds == 0:
        raise ValueError("American odds of 0 are not valid.")
    if odds < 0:
        return -odds / (-odds + 100)
    return 100 / (odds + 100)


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal (European) format.

    Examples:
        -150 → 1.6667
        +130 → 2.3000

    Raises:
        ValueError: If odds is zero.
    """
    if odds == 0:
        raise ValueError("American odds of 0 are not valid.")
    if odds < 0:
        return 1 + 100 / (-odds)
    return 1 + odds / 100
