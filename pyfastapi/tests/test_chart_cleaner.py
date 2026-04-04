from unittest.mock import patch

from jhora import const
from helpers import ChartCleaner


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

def test_clean_text_removes_unicode_strips_newlines():
    assert ChartCleaner.clean_text("  Sun\n☉Moon   ") == "Sun Moon"


def test_clean_text_strips_non_ascii_retrograde_symbol():
    assert ChartCleaner.clean_text("Saturn ℞\n") == "Saturn"


# ---------------------------------------------------------------------------
# format_response — happy path
# ---------------------------------------------------------------------------

def test_divisional_chart_keys_follow_configured_factors():
    raw_horoscope = (
        {"Raasi-Ascendant": "Aries 10 10 10"},
        [["Sun\nMoon"], ["Mars\nMercury"]],
        [0],
    )

    with patch.object(const, "division_chart_factors", [1, 9]):
        result = ChartCleaner.format_response(raw_horoscope)

    assert set(result["charts"].keys()) == {"D1", "D9"}
    assert result["charts"]["D1"] == [["Sun", "Moon"]]
    assert result["charts"]["D9"] == [["Mars", "Mercury"]]


def test_format_response_strips_non_ascii_retrograde_symbols_in_placements_and_charts():
    expected_chart_count = len(const.division_chart_factors)
    chart_entries = [
        ["Sun\nSaturn ℞"] + ["" for _ in range(11)]
        for _ in range(expected_chart_count)
    ]
    raw_horoscope = (
        {"Raasi-Saturn": "Capricorn ℞\n"},
        chart_entries,
        [0] * 12,
    )

    formatted = ChartCleaner.format_response(raw_horoscope)

    assert formatted["placements"]["Raasi-Saturn"] == "Capricorn"
    assert formatted["charts"]["D1"][0] == ["Sun", "Saturn"]


# ---------------------------------------------------------------------------
# format_response — fallback path
# ---------------------------------------------------------------------------

def test_fallback_house_parsing_and_label_derivation():
    raw_horoscope = (
        {
            "Raasi-Ascendant": "Aries 10 10 10",
            "D9-Ascendant": "Cancer 2 2 2",
        },
        [["Sun\n\n☉Moon"], [" Mars\nMercury\n"], ["Ketu\n\n"]],
        [0],
    )

    import helpers
    with (
        patch.object(const, "division_chart_factors", [1, 9]),
        patch.object(helpers.logger, "warning"),
    ):
        result = ChartCleaner.format_response(raw_horoscope)

    assert isinstance(result["charts"], list)
    assert result["charts"][0]["label"] == "Raasi"
    assert result["charts"][0]["factor"] == 1
    assert result["charts"][0]["houses"] == [["Sun", "Moon"]]
    assert result["charts"][1]["label"] == "D9"
    assert result["charts"][1]["factor"] == 9
    assert result["charts"][1]["houses"] == [["Mars", "Mercury"]]
    assert result["charts"][2]["label"] == "chart_3"
    assert result["charts"][2]["factor"] is None
    assert result["charts"][2]["houses"] == [["Ketu"]]


# ---------------------------------------------------------------------------
# _derive_chart_labels_from_placements
# ---------------------------------------------------------------------------

def test_derive_chart_labels_from_placements_returns_unique_labels():
    placements = {
        "Raasi-Ascendant": "Aries",
        "D9-Lagna": "Cancer",
        "D9-Ascendant": "Leo",
        "D2-Lagna": "Taurus",
        "something_else": "Gemini",
    }

    labels = ChartCleaner._derive_chart_labels_from_placements(placements)
    assert labels == ["Raasi", "D9", "D2"]


# ---------------------------------------------------------------------------
# _extract_factor
# ---------------------------------------------------------------------------

def test_extract_factor_parses_supported_labels():
    assert ChartCleaner._extract_factor("Raasi") == 1
    assert ChartCleaner._extract_factor("D9") == 9
    assert ChartCleaner._extract_factor("chart_1") is None


# ---------------------------------------------------------------------------
# _format_fallback_charts
# ---------------------------------------------------------------------------

def test_format_fallback_charts_uses_derived_labels_and_default_chart_names():
    placements = {"D2-Ascendant": "Aries", "D9-Lagna": "Cancer"}
    chart_entries = [["Sun"], ["Moon"], ["Mars"]]

    import helpers
    with (
        patch.object(const, "division_chart_factors", [1, 2, 9, 10]),
        patch.object(helpers.logger, "warning") as warning_mock,
    ):
        result = ChartCleaner._format_fallback_charts(
            placements=placements,
            chart_entries=chart_entries,
            expected_chart_count=4,
        )

    assert result[0]["label"] == "D2"
    assert result[1]["label"] == "D9"
    assert result[2]["label"] == "chart_3"
    assert result[2]["factor"] is None
    assert result[0]["houses"] == [["Sun"]]
    warning_mock.assert_called_once()
