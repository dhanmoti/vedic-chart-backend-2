from pathlib import Path
import sys

from jhora import const

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import ChartCleaner


def test_clean_text_strips_non_ascii_retrograde_symbol():
    assert ChartCleaner.clean_text("Saturn ℞\n") == "Saturn"


def test_format_response_strips_non_ascii_retrograde_symbols_in_placements_and_charts():
    expected_chart_count = len(const.division_chart_factors)
    chart_entries = [["Sun\nSaturn ℞"] + ["" for _ in range(11)] for _ in range(expected_chart_count)]
    raw_horoscope = (
        {"Raasi-Saturn": "Capricorn ℞\n"},
        chart_entries,
        [0] * 12,
    )

    formatted = ChartCleaner.format_response(raw_horoscope)

    assert formatted["placements"]["Raasi-Saturn"] == "Capricorn"
    assert formatted["charts"]["D1"][0] == ["Sun", "Saturn"]
