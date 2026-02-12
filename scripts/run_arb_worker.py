"""Run the arb-bot pipeline exactly once then exit.

Usage:
    python scripts/run_arb_worker.py
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("arb_worker")


def main() -> int:
    try:
        from cbb.bots.arb_bot import run_once

        run_once()
        logger.info("Done.")
        return 0
    except Exception:
        logger.exception("arb_worker failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
