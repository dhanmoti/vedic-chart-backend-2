import pytest

from services.chart_service import (
    parse_karaka_from_placement,
    parse_longitude_from_placement,
    traditional_parasara_hora_from_rasi_positions,
)


def test_traditional_parasara_hora_maps_only_to_cancer_and_leo():
    # [planet_id, (rasi_sign, longitude_within_sign)]
    rasi_positions = [
        ["L", (0, 10.0)],  # odd sign, first half  => Leo (4)
        [0, (0, 20.0)],    # odd sign, second half => Cancer (3)
        [1, (1, 10.0)],    # even sign, first half => Cancer (3)
        [2, (1, 20.0)],    # even sign, second half => Leo (4)
    ]

    d2_chart = traditional_parasara_hora_from_rasi_positions(rasi_positions, ["Sun", "Moon", "Mars"])

    non_empty_houses = {idx for idx, house in enumerate(d2_chart) if house}
    assert non_empty_houses == {3, 4}
    assert d2_chart[4] == ["Ascendant", "Mars"]
    assert d2_chart[3] == ["Sun", "Moon"]


# parse_karaka_from_placement


def test_parse_karaka_from_placement_extracts_trailing_parenthetical():
    value = "♀︎Virgo 3° 36’ 14\" (Putra Karaka)"
    assert parse_karaka_from_placement(value) == "Putra Karaka"


def test_parse_karaka_from_placement_returns_none_without_parenthetical():
    assert parse_karaka_from_placement("Virgo 3° 36’ 14\"") is None


def test_parse_karaka_from_placement_matches_only_the_trailing_group():
    value = "Virgo (some note) (Putra Karaka)"
    assert parse_karaka_from_placement(value) == "Putra Karaka"


# parse_longitude_from_placement


def test_parse_longitude_from_placement_parses_degrees_minutes_seconds():
    value = "♀︎Virgo 3° 36’ 14\" (Putra Karaka)"
    longitude = parse_longitude_from_placement(value)
    # Virgo = sign index 5 -> 5*30 + 3 + 36/60 + 14/3600
    assert longitude == pytest.approx(153.6039, abs=1e-3)


def test_parse_longitude_from_placement_defaults_seconds_to_zero_when_absent():
    longitude = parse_longitude_from_placement("Aries 12-34")
    assert longitude == pytest.approx(12 + 34 / 60.0, abs=1e-6)


def test_parse_longitude_from_placement_returns_none_for_unmatched_string():
    assert parse_longitude_from_placement("not a placement string") is None


def test_parse_longitude_from_placement_prefers_longest_sign_match():
    # "Ari" is a prefix-substring of "Aries"; without longest-match-first
    # ordering this would wrongly match "Ari" -> index 99 instead of "Aries" -> 0.
    longitude = parse_longitude_from_placement(
        "Aries 1-2-3", sign_to_index={"Ari": 99}
    )
    assert longitude == pytest.approx(1 + 2 / 60.0 + 3 / 3600.0, abs=1e-6)


def test_parse_longitude_from_placement_supports_custom_sign_map():
    longitude = parse_longitude_from_placement(
        "Mesha 5-0-0", sign_to_index={"Mesha": 0}
    )
    assert longitude == pytest.approx(5.0, abs=1e-6)
