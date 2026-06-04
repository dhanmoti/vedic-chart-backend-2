"""
Tests for non-English language support in /horoscope.

Covers two concerns:
  1. Benchmark regression: snapshot-matches stored fixture for Hindi and Tamil.
  2. Structural invariants: properties that must hold for any non-English response
     (planet count, sign constraints, Unicode names, D2/D3 completeness, etc.).
"""
import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "horoscope_language_benchmark_cases.json"

_HI_PLANET_NAMES = ["सूर्य", "चंद्रमा", "मंगल", "बुध", "बृहस्पति", "शुक्र", "शनि", "राहु", "केतु"]
_TA_PLANET_NAMES = ["சூரியன்", "சந்திரன்", "செவ்வாய்", "புதன்", "குரு", "சுக்ரன்", "சனி", "ராகு", "கேது"]


# ---------------------------------------------------------------------------
# Benchmark regression
# ---------------------------------------------------------------------------

def test_horoscope_language_benchmark_matches_fixture(app_client):
    cases = json.loads(FIXTURE_PATH.read_text())
    assert len(cases) == 8, f"Expected 8 language benchmark cases, got {len(cases)}"

    for case in cases:
        response = app_client.post("/horoscope", json=case["input"])
        lang = case["input"]["language"]
        assert response.status_code == case["status_code"], f"case_id={case['case_id']} lang={lang}"
        assert response.json() == case["expected"], f"case_id={case['case_id']} lang={lang}"


# ---------------------------------------------------------------------------
# Structural invariants — shared payload
# ---------------------------------------------------------------------------

@pytest.fixture
def hi_payload():
    return {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": "hi",
        "chart_style": "south",
    }


@pytest.fixture
def ta_payload():
    return {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": "ta",
        "chart_style": "south",
    }


# ---------------------------------------------------------------------------
# Planet names are in the requested language
# ---------------------------------------------------------------------------

def test_horoscope_hindi_returns_hindi_planet_names(app_client, hi_payload):
    response = app_client.post("/horoscope", json=hi_payload)
    assert response.status_code == 200

    planets = response.json()["data"]["planets"]
    assert len(planets) == 9
    actual_names = [p["name"] for p in planets]
    assert actual_names == _HI_PLANET_NAMES, (
        f"Expected Hindi planet names, got {actual_names}"
    )


def test_horoscope_tamil_returns_tamil_planet_names(app_client, ta_payload):
    response = app_client.post("/horoscope", json=ta_payload)
    assert response.status_code == 200

    planets = response.json()["data"]["planets"]
    assert len(planets) == 9
    actual_names = [p["name"] for p in planets]
    assert actual_names == _TA_PLANET_NAMES, (
        f"Expected Tamil planet names, got {actual_names}"
    )


def test_horoscope_non_english_planet_names_are_not_english(app_client, hi_payload, ta_payload):
    english_names = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
                     "Raagu", "Kethu"}
    for payload in [hi_payload, ta_payload]:
        response = app_client.post("/horoscope", json=payload)
        names = {p["name"] for p in response.json()["data"]["planets"]}
        overlap = names & english_names
        assert not overlap, (
            f"lang={payload['language']}: found English names in response: {overlap}"
        )


# ---------------------------------------------------------------------------
# Sign names are in the requested language
# ---------------------------------------------------------------------------

def test_horoscope_hindi_sign_names_are_not_english(app_client, hi_payload):
    response = app_client.post("/horoscope", json=hi_payload)
    assert response.status_code == 200

    data = response.json()["data"]
    english_signs = {
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    }

    # Ascendant sign
    assert data["ascendant"]["sign"] not in english_signs, (
        f"Ascendant sign should be Hindi, got {data['ascendant']['sign']}"
    )

    # Planet signs
    for p in data["planets"]:
        assert p["sign"] not in english_signs, f"Planet {p['id']} sign is English: {p['sign']}"


def test_horoscope_tamil_sign_names_are_not_english(app_client, ta_payload):
    response = app_client.post("/horoscope", json=ta_payload)
    assert response.status_code == 200

    data = response.json()["data"]
    english_signs = {
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    }

    assert data["ascendant"]["sign"] not in english_signs
    for p in data["planets"]:
        assert p["sign"] not in english_signs, f"Planet {p['id']} sign is English: {p['sign']}"


# ---------------------------------------------------------------------------
# Divisional chart completeness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_returns_all_divisional_charts(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    divisions = response.json()["data"]["divisions"]
    assert len(divisions) >= 20, (
        f"lang={language}: expected 20+ divisions, got {len(divisions)}: {sorted(divisions)}"
    )
    for div in ["D2", "D3", "D4", "D7", "D9", "D12", "D16", "D60"]:
        assert div in divisions, f"lang={language}: missing division {div}"


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_divisional_charts_have_9_planets(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    divisions = response.json()["data"]["divisions"]
    for div_code in ["D2", "D3", "D9"]:
        planets = divisions.get(div_code, {}).get("planets", [])
        assert len(planets) == 9, (
            f"lang={language} {div_code}: expected 9 planets, got {len(planets)}"
        )


# ---------------------------------------------------------------------------
# D2 must only place planets in Cancer (3) or Leo (4) — Traditional Parasara
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_d2_planets_are_cancer_or_leo(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    d2_planets = response.json()["data"]["divisions"]["D2"]["planets"]
    assert len(d2_planets) == 9
    for p in d2_planets:
        assert p["sign_index"] in {3, 4}, (
            f"lang={language}: D2 planet {p['id']} has sign_index={p['sign_index']}, "
            f"expected 3 (Cancer) or 4 (Leo)"
        )


# ---------------------------------------------------------------------------
# Divisional planet sign names match the requested language
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_divisional_sign_names_are_not_english(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    english_signs = {
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    }
    divisions = response.json()["data"]["divisions"]
    for div_code in ["D3", "D9"]:
        for p in divisions[div_code]["planets"]:
            assert p["sign"] not in english_signs, (
                f"lang={language} {div_code} planet {p['id']}: sign is English: {p['sign']}"
            )


# ---------------------------------------------------------------------------
# house and sign_index are always valid regardless of language
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_divisional_planet_fields_are_valid(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    divisions = response.json()["data"]["divisions"]
    for div_code, div_data in divisions.items():
        for p in div_data["planets"]:
            assert 0 <= p["sign_index"] <= 11, f"{div_code} planet {p['id']} bad sign_index"
            assert 1 <= p["house"] <= 12, f"{div_code} planet {p['id']} bad house"
            assert 0.0 <= p["longitude_in_sign"] < 30.0, f"{div_code} planet {p['id']} bad longitude"


# ---------------------------------------------------------------------------
# planet_names and sign_names are consistent between D1 (planets list) and divisions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["hi", "ta"])
def test_horoscope_non_english_division_planet_names_match_d1(app_client, language):
    payload = {
        "dob": "1991-11-13",
        "time": "15:00",
        "lat": 1.11,
        "lng": 89.88,
        "tz": 8.0,
        "language": language,
        "chart_style": "south",
    }
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    data = response.json()["data"]
    d1_names = {p["id"]: p["name"] for p in data["planets"]}
    d1_symbols = {p["id"]: p["symbol"] for p in data["planets"]}

    # D9 planet names and symbols must match D1 (id → name mapping is language-invariant)
    for p in data["divisions"]["D9"]["planets"]:
        assert p["name"] == d1_names[p["id"]], (
            f"lang={language} D9 planet {p['id']} name mismatch: {p['name']} vs {d1_names[p['id']]}"
        )
        assert p["symbol"] == d1_symbols[p["id"]], (
            f"lang={language} D9 planet {p['id']} symbol mismatch"
        )
