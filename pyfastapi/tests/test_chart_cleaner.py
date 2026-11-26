from helpers import ChartCleaner


def test_split_name_symbol_separates_trailing_planet_symbol():
    assert ChartCleaner.split_name_symbol(" Sun☉ ") == ("Sun", "☉")
    assert ChartCleaner.split_name_symbol("Sun") == ("Sun", "")


def test_clean_unicode_preserves_script_and_removes_newlines():
    assert ChartCleaner.clean_unicode(" सूर्य\n") == "सूर्य"


def test_strip_zodiac_prefix_removes_symbol_and_variation_selector():
    assert ChartCleaner.strip_zodiac_prefix("♑︎मकर") == "मकर"
