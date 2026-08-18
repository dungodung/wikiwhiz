from backend.app.lib.slot_pattern import tokenize_title_to_slots


def test_single_word():
    assert tokenize_title_to_slots("Einstein") == [{"type": "word", "len": 8}]


def test_multi_word_has_space_tokens():
    slots = tokenize_title_to_slots("Albert Einstein")
    assert slots == [
        {"type": "word", "len": 6},
        {"type": "space"},
        {"type": "word", "len": 8},
    ]


def test_punctuation_preserved():
    slots = tokenize_title_to_slots("Spider-Man")
    assert slots == [
        {"type": "word", "len": 6},
        {"type": "punct", "char": "-"},
        {"type": "word", "len": 3},
    ]
