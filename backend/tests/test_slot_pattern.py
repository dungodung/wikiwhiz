from backend.app.lib.slot_pattern import normalize_to_tiles, tile_shape


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


def test_quotation_marks_and_digits_are_discarded():
    assert tile_shape('The "Great" Escape (1963)') == "L" * len("The Great Escape ()")


def test_diacritics_normalize_to_ascii():
    assert normalize_to_tiles("Café") == "Cafe"
    assert tile_shape("Café") == "LLLL"


def test_manual_transliteration_for_non_decomposable_letters():
    assert normalize_to_tiles("Straße") == "Strasse"
    assert normalize_to_tiles("Bjørn") == "Bjorn"


def test_normalize_to_tiles_preserves_case_and_kept_punctuation():
    assert normalize_to_tiles("Spider-Man") == "Spider-Man"
    assert normalize_to_tiles("Albert Einstein") == "Albert Einstein"
