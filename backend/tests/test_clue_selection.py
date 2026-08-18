from backend.app.lib.clue_selection import compute_clue_order


def test_deterministic_for_same_seed():
    rows = [{"id": i, "reveal_rank_hint": (i % 7) + 1} for i in range(1, 9)]
    order_a = compute_clue_order(rows, seed=42)
    order_b = compute_clue_order(rows, seed=42)
    assert order_a == order_b


def test_varies_by_seed():
    rows = [{"id": i, "reveal_rank_hint": (i % 7) + 1} for i in range(1, 9)]
    order_a = compute_clue_order(rows, seed=1)
    order_b = compute_clue_order(rows, seed=2)
    assert order_a != order_b


def test_truncated_to_max_seven():
    rows = [{"id": i, "reveal_rank_hint": 4} for i in range(1, 11)]
    order = compute_clue_order(rows, seed=1)
    assert len(order) == 7
