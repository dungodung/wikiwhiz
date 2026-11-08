from backend.app.lib.similarity import bucket_lexical, score_lexical


def test_exact_match_scores_top_bucket():
    assert bucket_lexical(score_lexical("Albert Einstein", "Albert Einstein")) == 19


def test_reordered_words_score_high():
    raw = score_lexical("Einstein Albert", "Albert Einstein")
    assert raw > 0.8


def test_unrelated_text_scores_low():
    raw = score_lexical("Banana Republic", "Albert Einstein")
    assert bucket_lexical(raw) <= 10


def test_disjoint_character_sets_score_near_zero():
    raw = score_lexical("12345678", "qwertzuiop")
    assert bucket_lexical(raw) < 3


def test_diacritics_and_case_are_ignored():
    raw = score_lexical("cafe", "CAFÉ")
    assert raw == 1.0


def test_first_letter_typo_that_changes_word_sort_order_still_scores_high():
    # "comodo" sorts before "dragon" but "komodo" sorts after it, which used
    # to wreck token_sort_ratio and drop this one-letter typo to "Warm".
    assert bucket_lexical(score_lexical("Comodo dragon", "Komodo dragon")) >= 17
