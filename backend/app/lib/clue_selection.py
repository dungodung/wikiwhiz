"""Seeded, deterministic-per-day clue reveal ordering.

Computed once, at scheduling time (scripts/db_schedule_challenge.py), never
per-request: request handlers just index into the frozen result stored on
DailyChallenge.clue_order. This keeps a page refresh mid-game from reshuffling
clues, keeps historical days stable even if this algorithm changes later, and
still varies the order day to day.
"""

import random

MIN_CLUES = 5
MAX_CLUES = 7


def compute_clue_order(clue_rows: list[dict], seed: int) -> list[int]:
    """clue_rows: [{"id": int, "reveal_rank_hint": int}, ...] (non-leaking clues only).

    Returns an ordered list of clue ids, truncated to MIN_CLUES..MAX_CLUES.
    """
    rng = random.Random(seed)
    jittered = [
        (row["reveal_rank_hint"] + rng.uniform(-0.5, 0.5), row["id"]) for row in clue_rows
    ]
    jittered.sort(key=lambda pair: pair[0])
    ordered_ids = [clue_id for _, clue_id in jittered]
    return ordered_ids[:MAX_CLUES] if len(ordered_ids) > MAX_CLUES else ordered_ids
