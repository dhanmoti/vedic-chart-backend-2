import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.panchanga as panchanga_router
import services.panchanga_service as panchanga_service


@pytest.fixture
def panchanga_payload():
    return {
        "date": "2025-01-01",
        "time": "06:00",
        "lat": 12.9716,
        "lng": 77.5946,
        "tz": 5.5,
        "language": "en",
    }


def test_panchanga_requires_app_check_header(panchanga_payload):
    from main import app
    with TestClient(app) as client:
        response = client.post("/panchanga", json=panchanga_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_panchanga_returns_cached_payload_when_available(app_client, panchanga_payload):
    cached = {
        "status": "success",
        "data": {
            "date": "2025-01-01",
            "vaara": "Wednesday",
            "tithi": "Dwitiya",
            "tithi_index": 2,
            "nakshatra": "Rohini",
            "nakshatra_index": 4,
            "yoga": "Shiva",
            "yoga_index": 20,
            "karana": "Bava",
            "karana_index": 2,
            "lunar_month": "Margashirsha",
            "sunrise": "06:45",
            "sunset": "18:00",
        },
    }
    with patch.object(panchanga_router.CACHE_SERVICE, "get", return_value=cached) as mock_get:
        response = app_client.post("/panchanga", json=panchanga_payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_panchanga_rejects_missing_date(app_client, panchanga_payload):
    payload = {k: v for k, v in panchanga_payload.items() if k != "date"}
    response = app_client.post("/panchanga", json=payload)
    assert response.status_code == 422


def test_panchanga_rejects_invalid_date_format(app_client, panchanga_payload):
    payload = {**panchanga_payload, "date": "01/01/2025"}
    response = app_client.post("/panchanga", json=payload)
    assert response.status_code == 422


def test_panchanga_rejects_out_of_range_lat(app_client, panchanga_payload):
    payload = {**panchanga_payload, "lat": 999.0}
    response = app_client.post("/panchanga", json=payload)
    assert response.status_code == 422


def test_panchanga_returns_500_on_service_failure(app_client, panchanga_payload):
    with patch.object(panchanga_router.CACHE_SERVICE, "get", return_value=None), \
         patch.object(panchanga_service.drik, "tithi", side_effect=RuntimeError("boom")):
        response = app_client.post("/panchanga", json=panchanga_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating panchanga."


def test_panchanga_returns_expected_response_shape(app_client, panchanga_payload):
    response = app_client.post("/panchanga", json=panchanga_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["date"] == "2025-01-01"
    assert "vaara" in data
    assert "tithi" in data
    assert isinstance(data["tithi_index"], int)
    assert "nakshatra" in data
    assert isinstance(data["nakshatra_index"], int)
    assert "yoga" in data
    assert isinstance(data["yoga_index"], int)
    assert "karana" in data
    assert "lunar_month" in data
    assert "sunrise" in data
    assert "sunset" in data
    assert ":" in data["sunrise"]
    assert ":" in data["sunset"]
