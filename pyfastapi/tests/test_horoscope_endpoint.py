import json
from pathlib import Path
from unittest.mock import patch

import pytest

import routers.horoscope as horoscope_router
import services.horoscope_service as horoscope_service


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "horoscope_benchmark_cases.json"


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

    # No dependency override — App Check must be enforced.
    with TestClient(app) as client:
        response = client.post("/horoscope", json=valid_payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_health_check_endpoint(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online"}


def test_horoscope_returns_cached_payload_when_available(app_client, valid_payload):
    cached_payload = {
        "status": "success",
        "data": {
            "placements": {},
            "charts": {},
            "house_indices": [],
            "ascendant_lord": None,
            "ascendant_nakshatra": None,
            "nakshatras": {"Raasi-Lagna": None},
        },
    }

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
        patch.object(horoscope_router.CACHE_SERVICE, "get", return_value=cached_payload) as mock_get,
    ):
        response = app_client.post("/horoscope", json=valid_payload)

    assert response.status_code == 200
    assert response.json() == cached_payload
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


def test_horoscope_returns_500_on_chart_generation_failure(app_client, valid_payload):
    with patch.object(horoscope_service, "Horoscope", side_effect=RuntimeError("boom")):
        response = app_client.post("/horoscope", json=valid_payload)

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating chart."
