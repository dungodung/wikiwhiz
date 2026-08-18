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
