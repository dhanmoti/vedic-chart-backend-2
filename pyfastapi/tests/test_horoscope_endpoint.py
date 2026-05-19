import json
from pathlib import Path
from unittest.mock import patch

import pytest

import routers.horoscope as horoscope_router
import services.horoscope_service as horoscope_service


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "horoscope_benchmark_cases.json"

_MINIMAL_CACHED_PAYLOAD = {
    "status": "success",
    "data": {
        "meta": {"chart_style": "south", "language": "en"},
        "ascendant": {
            "sign": "Aries",
            "sign_index": 0,
            "sign_symbol": "♈",
            "longitude": 15.5,
            "longitude_in_sign": 15.5,
            "lord": "Mars",
            "lord_symbol": "♂",
            "nakshatra": {
                "name": "Aswini",
                "index": 1,
                "pada": 2,
                "lord": "Kethu",
                "lord_symbol": "☋",
            },
        },
        "planets": [],
        "charts": {},
        "house_signs": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "divisions": {},
    },
}


def test_horoscope_benchmark_outputs_match_fixture_for_10_variations(app_client):
    cases = json.loads(FIXTURE_PATH.read_text())
    assert len(cases) == 10

    for case in cases:
        response = app_client.post("/horoscope", json=case["input"])
        assert response.status_code == case["status_code"], f"case_id={case['case_id']}"
        assert response.json() == case["expected"], f"case_id={case['case_id']}"


def test_horoscope_requires_app_check_header(valid_payload):
    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.post("/horoscope", json=valid_payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_health_check_endpoint(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online"}


def test_horoscope_returns_cached_payload_when_available(app_client, valid_payload):
    with (
        patch.object(
            horoscope_router.CACHE_SERVICE,
            "normalize_key_fields",
            return_value={
                "dob": valid_payload["dob"],
                "time": valid_payload["time"],
                "lat": round(valid_payload["lat"], horoscope_router.CACHE_SERVICE.config.lat_lng_precision),
                "lng": round(valid_payload["lng"], horoscope_router.CACHE_SERVICE.config.lat_lng_precision),
                "tz": round(valid_payload["tz"], horoscope_router.CACHE_SERVICE.config.tz_precision),
                "language": valid_payload["language"].strip().lower(),
            },
        ),
        patch.object(horoscope_router.CACHE_SERVICE, "build_cache_key", return_value="dummy_key"),
        patch.object(
            horoscope_router.CACHE_SERVICE, "get", return_value=_MINIMAL_CACHED_PAYLOAD
        ) as mock_get,
    ):
        response = app_client.post("/horoscope", json=valid_payload)

    assert response.status_code == 200
    assert response.json() == _MINIMAL_CACHED_PAYLOAD
    mock_get.assert_called_once()


def test_horoscope_rejects_invalid_dob_format(app_client, valid_payload):
    payload = {**valid_payload, "dob": "01-01-1990"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 422


def test_horoscope_rejects_invalid_time_format(app_client, valid_payload):
    payload = {**valid_payload, "time": "24:00"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 422


def test_horoscope_rejects_missing_required_field(app_client, valid_payload):
    payload = {**valid_payload}
    payload.pop("lat")
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 422
    assert any(error["loc"][-1] == "lat" for error in response.json()["detail"])


def test_horoscope_rejects_out_of_range_coordinates(app_client, valid_payload):
    payload = {**valid_payload, "lat": 99.0, "lng": 200.0, "tz": 20.0}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 422
    assert any(
        "lat" in error["loc"] or "lng" in error["loc"] or "tz" in error["loc"]
        for error in response.json()["detail"]
    )


def test_horoscope_rejects_invalid_chart_style(app_client, valid_payload):
    payload = {**valid_payload, "chart_style": "diagonal"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 422


def test_horoscope_returns_500_on_chart_generation_failure(app_client, valid_payload):
    with patch.object(horoscope_service, "Horoscope", side_effect=RuntimeError("boom")):
        response = app_client.post("/horoscope", json=valid_payload)

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating chart."


def test_horoscope_returns_expected_response_shape(app_client, valid_payload):
    response = app_client.post("/horoscope", json=valid_payload)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert data["meta"]["chart_style"] == "south"
    assert data["meta"]["language"] == "en"

    asc = data["ascendant"]
    assert isinstance(asc["sign"], str)
    assert isinstance(asc["sign_index"], int)
    assert isinstance(asc["sign_symbol"], str)
    assert isinstance(asc["longitude"], float)
    assert isinstance(asc["longitude_in_sign"], float)
    assert isinstance(asc["lord"], str)
    assert isinstance(asc["lord_symbol"], str)
    assert isinstance(asc["nakshatra"]["name"], str)
    assert isinstance(asc["nakshatra"]["index"], int)
    assert isinstance(asc["nakshatra"]["pada"], int)

    planets = data["planets"]
    assert len(planets) == 9
    first = planets[0]
    assert first["id"] == 0
    assert first["name"] == "Sun"
    assert first["symbol"] == "☉"
    assert isinstance(first["sign"], str)
    assert isinstance(first["sign_index"], int)
    assert isinstance(first["house"], int) and 1 <= first["house"] <= 12
    assert isinstance(first["longitude"], float)
    assert isinstance(first["is_retrograde"], bool)
    assert isinstance(first["daily_motion"], float)
    assert first["dignity"]["status"] in {
        "exalted", "own_sign", "moolatrikona", "friend", "neutral", "enemy", "debilitated"
    }
    assert 0 <= first["dignity"]["score"] <= 5
    assert isinstance(first["nakshatra"]["name"], str)

    house_signs = data["house_signs"]
    assert len(house_signs) == 12
    assert all(0 <= s <= 11 for s in house_signs)

    assert "D1" in data["charts"]
    assert len(data["charts"]["D1"]) == 12

    assert "divisions" in data
    assert "D9" in data["divisions"]
    d9_planets = data["divisions"]["D9"]["planets"]
    assert len(d9_planets) == 9
    dp = d9_planets[0]
    assert isinstance(dp["id"], int)
    assert isinstance(dp["name"], str)
    assert isinstance(dp["symbol"], str)
    assert isinstance(dp["sign"], str)
    assert 0 <= dp["sign_index"] <= 11
    assert 0.0 <= dp["longitude_in_sign"] < 30.0
    assert 1 <= dp["house"] <= 12
    assert "D2" in data["divisions"]
    assert len(data["divisions"]["D2"]["planets"]) == 9
    for d2p in data["divisions"]["D2"]["planets"]:
        assert d2p["sign_index"] in {3, 4}, f"D2 planet must be Cancer or Leo, got {d2p['sign_index']}"


def test_horoscope_north_style_fixes_rahu_ketu_names(app_client, valid_payload):
    payload = {**valid_payload, "chart_style": "north", "language": "en"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    planets = response.json()["data"]["planets"]
    rahu = planets[7]
    ketu = planets[8]
    assert rahu["name"] == "Rahu", f"Expected 'Rahu', got '{rahu['name']}'"
    assert ketu["name"] == "Ketu", f"Expected 'Ketu', got '{ketu['name']}'"


def test_horoscope_north_style_uses_sanskrit_nakshatra_names(app_client, valid_payload):
    payload = {**valid_payload, "chart_style": "north", "language": "en"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    planets = response.json()["data"]["planets"]
    all_nakshatra_names = {p["nakshatra"]["name"] for p in planets}
    # None of the Tamil-style names should appear in north style
    tamil_style = {"Aswini", "Karthigai", "Mrigasheesham", "Thiruvaathirai", "Punarpoosam"}
    assert not all_nakshatra_names.intersection(tamil_style), (
        f"Tamil names found in north style: {all_nakshatra_names.intersection(tamil_style)}"
    )


def test_horoscope_south_style_preserves_tamil_rahu_ketu(app_client, valid_payload):
    payload = {**valid_payload, "chart_style": "south", "language": "en"}
    response = app_client.post("/horoscope", json=payload)
    assert response.status_code == 200

    planets = response.json()["data"]["planets"]
    rahu = planets[7]
    ketu = planets[8]
    assert rahu["name"] == "Raagu", f"Expected 'Raagu', got '{rahu['name']}'"
    assert ketu["name"] == "Kethu", f"Expected 'Kethu', got '{ketu['name']}'"
