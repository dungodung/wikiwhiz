from backend.app.lib.slot_pattern import normalize_to_tiles, tile_shape, word_count


def test_single_word():
    assert tile_shape("Einstein") == "LLLLLLLL"


def test_space_counts_as_a_tile_but_is_not_revealed():
    # 6 + 1 space + 8 = 15 tiles, all blank -- nothing about the shape
    # (including where the space falls) is pre-revealed.
    assert tile_shape("Albert Einstein") == "L" * 15


def test_dash_counts_as_a_tile_but_is_not_revealed():
    assert tile_shape("Spider-Man") == "L" * 10


def test_comma_and_parentheses_count_as_tiles_but_are_not_revealed():
    assert tile_shape("Paris, Texas") == "L" * 12
    assert tile_shape("Mercury (element)") == "L" * 17


def test_quotation_marks_are_discarded_but_digits_are_kept():
    assert tile_shape('The "Great" Escape (1963)') == "L" * len("The Great Escape (1963)")
    assert normalize_to_tiles("Apollo 11") == "Apollo 11"


def test_diacritics_normalize_to_ascii():
    assert normalize_to_tiles("Café") == "Cafe"
    assert tile_shape("Café") == "LLLL"


def test_manual_transliteration_for_non_decomposable_letters():
    assert normalize_to_tiles("Straße") == "Strasse"
    assert normalize_to_tiles("Bjørn") == "Bjorn"


def test_normalize_to_tiles_preserves_case_and_kept_punctuation():
    assert normalize_to_tiles("Spider-Man") == "Spider-Man"
    assert normalize_to_tiles("Albert Einstein") == "Albert Einstein"


def test_word_count_single_word_regardless_of_internal_punctuation():
    assert word_count("Armageddon") == 1
    assert word_count("Spider-Man") == 1


def test_word_count_splits_on_space_even_before_kept_punctuation():
    # The space before "(element)" is still a space -- kept punctuation
    # only avoids splitting when it isn't preceded by one.
    assert word_count("Mercury (element)") == 2


def test_word_count_splits_only_on_space():
    assert word_count("George Clooney") == 2
    assert word_count("Albert Einstein") == 2
    assert word_count("Apollo 11") == 2


def test_word_count_three_words():
    assert word_count("The Great Escape") == 3
