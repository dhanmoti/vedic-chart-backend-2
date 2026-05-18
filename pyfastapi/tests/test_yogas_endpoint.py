import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.yogas as yogas_router
import services.yogas_service as yogas_service


def test_yogas_requires_app_check_header(valid_payload):
    from main import app
    with TestClient(app) as client:
        response = client.post("/yogas", json=valid_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_yogas_returns_cached_payload_when_available(app_client, valid_payload):
    cached = {
        "status": "success",
        "data": {
            "yogas": [{"name": "Ruchaka", "planet": "Mars", "present": True}],
        },
    }
    with patch.object(yogas_router.CACHE_SERVICE, "get", return_value=cached) as mock_get:
        response = app_client.post("/yogas", json=valid_payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_yogas_rejects_missing_required_field(app_client, valid_payload):
    payload = {k: v for k, v in valid_payload.items() if k != "dob"}
    response = app_client.post("/yogas", json=payload)
    assert response.status_code == 422
    locs = [err["loc"] for err in response.json()["detail"]]
    assert any("dob" in loc for loc in locs)


def test_yogas_rejects_out_of_range_inputs(app_client, valid_payload):
    payload = {**valid_payload, "lng": 999.0}
    response = app_client.post("/yogas", json=payload)
    assert response.status_code == 422


def test_yogas_returns_500_on_service_failure(app_client, valid_payload):
    with patch.object(yogas_router.CACHE_SERVICE, "get", return_value=None), \
         patch.object(yogas_service.drik, "Place", side_effect=RuntimeError("boom")):
        response = app_client.post("/yogas", json=valid_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating yogas."


def test_yogas_returns_expected_response_shape(app_client, valid_payload):
    response = app_client.post("/yogas", json=valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "yogas" in data
    assert isinstance(data["yogas"], list)
    assert len(data["yogas"]) == 7
    yoga = data["yogas"][0]
    assert "name" in yoga
    assert "present" in yoga
    assert isinstance(yoga["present"], bool)
    yoga_names = [y["name"] for y in data["yogas"]]
    assert "Ruchaka" in yoga_names
    assert "Hamsa" in yoga_names
