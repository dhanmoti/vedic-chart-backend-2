import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.transit as transit_router
import services.gochar_service as gochar_service
import services.varsha_service as varsha_service


# --- Gochar tests ---

def test_gochar_requires_app_check_header(valid_payload):
    from main import app
    payload = {**valid_payload, "transit_date": "2025-01-01"}
    with TestClient(app) as client:
        response = client.post("/transit/gochar", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_gochar_returns_cached_payload_when_available(app_client, valid_payload):
    cached = {
        "status": "success",
        "data": {
            "transit_date": "2025-01-01",
            "natal_lagna_sign": 0,
            "natal_moon_sign": 1,
            "transit_planets": [],
        },
    }
    payload = {**valid_payload, "transit_date": "2025-01-01"}
    with patch.object(transit_router.GOCHAR_CACHE, "get", return_value=cached) as mock_get:
        response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_gochar_rejects_missing_transit_date(app_client, valid_payload):
    response = app_client.post("/transit/gochar", json=valid_payload)
    assert response.status_code == 422


def test_gochar_rejects_invalid_transit_date_format(app_client, valid_payload):
    payload = {**valid_payload, "transit_date": "01-01-2025"}
    response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 422


def test_gochar_rejects_out_of_range_lat(app_client, valid_payload):
    payload = {**valid_payload, "transit_date": "2025-01-01", "lat": 999.0}
    response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 422


def test_gochar_returns_500_on_service_failure(app_client, valid_payload):
    payload = {**valid_payload, "transit_date": "2025-01-01"}
    with patch.object(transit_router.GOCHAR_CACHE, "get", return_value=None), \
         patch.object(gochar_service.charts, "rasi_chart", side_effect=RuntimeError("boom")):
        response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating gochar."


def test_gochar_north_style_en_uses_corrected_planet_names(app_client, valid_payload):
    payload = {**valid_payload, "transit_date": "2025-01-01", "chart_style": "north", "language": "en"}
    response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 200
    planet_names = [p["name"] for p in response.json()["data"]["transit_planets"]]
    assert "Rahu" in planet_names
    assert "Ketu" in planet_names
    assert "Raagu" not in planet_names
    assert "Kethu" not in planet_names


def test_gochar_returns_expected_response_shape(app_client, valid_payload):
    payload = {**valid_payload, "transit_date": "2025-01-01"}
    response = app_client.post("/transit/gochar", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "transit_date" in data
    assert "natal_lagna_sign" in data
    assert "natal_moon_sign" in data
    assert "transit_planets" in data
    assert isinstance(data["transit_planets"], list)
    assert len(data["transit_planets"]) == 9
    planet = data["transit_planets"][0]
    assert "name" in planet
    assert "longitude" in planet
    assert "sign" in planet
    assert "house_from_lagna" in planet
    assert "house_from_moon" in planet
    assert "is_retrograde" in planet


# --- Varsha tests ---

def test_varsha_requires_app_check_header(valid_payload):
    from main import app
    payload = {**valid_payload, "year": 35}
    with TestClient(app) as client:
        response = client.post("/transit/varsha", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_varsha_returns_cached_payload_when_available(app_client, valid_payload):
    cached = {
        "status": "success",
        "data": {
            "year": 35,
            "chart_date": "2025-01-01",
            "chart": [[] for _ in range(12)],
        },
    }
    payload = {**valid_payload, "year": 35}
    with patch.object(transit_router.VARSHA_CACHE, "get", return_value=cached) as mock_get:
        response = app_client.post("/transit/varsha", json=payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_varsha_rejects_missing_year(app_client, valid_payload):
    response = app_client.post("/transit/varsha", json=valid_payload)
    assert response.status_code == 422


def test_varsha_rejects_out_of_range_year(app_client, valid_payload):
    payload = {**valid_payload, "year": 150}
    response = app_client.post("/transit/varsha", json=payload)
    assert response.status_code == 422


def test_varsha_returns_500_on_service_failure(app_client, valid_payload):
    payload = {**valid_payload, "year": 35}
    with patch.object(transit_router.VARSHA_CACHE, "get", return_value=None), \
         patch.object(varsha_service.tajaka, "annual_chart", side_effect=RuntimeError("boom")):
        response = app_client.post("/transit/varsha", json=payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating varsha."


def test_varsha_returns_expected_response_shape(app_client, valid_payload):
    payload = {**valid_payload, "year": 35}
    response = app_client.post("/transit/varsha", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["year"] == 35
    assert "chart_date" in data
    assert "chart" in data
    assert isinstance(data["chart"], list)
    assert len(data["chart"]) == 12
