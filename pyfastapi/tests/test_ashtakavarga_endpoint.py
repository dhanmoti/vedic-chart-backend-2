import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.ashtakavarga as ashtakavarga_router
import services.ashtakavarga_service as ashtakavarga_service


def test_ashtakavarga_requires_app_check_header(valid_payload):
    from main import app
    with TestClient(app) as client:
        response = client.post("/ashtakavarga", json=valid_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_ashtakavarga_returns_cached_payload_when_available(app_client, valid_payload):
    cached = {
        "status": "success",
        "data": {
            "binna": {"Sun": [3] * 12},
            "samudaya": [28] * 12,
        },
    }
    with patch.object(ashtakavarga_router.CACHE_SERVICE, "get", return_value=cached) as mock_get:
        response = app_client.post("/ashtakavarga", json=valid_payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_ashtakavarga_rejects_missing_required_field(app_client, valid_payload):
    payload = {k: v for k, v in valid_payload.items() if k != "lat"}
    response = app_client.post("/ashtakavarga", json=payload)
    assert response.status_code == 422
    locs = [err["loc"] for err in response.json()["detail"]]
    assert any("lat" in loc for loc in locs)


def test_ashtakavarga_rejects_out_of_range_inputs(app_client, valid_payload):
    payload = {**valid_payload, "tz": 99.0}
    response = app_client.post("/ashtakavarga", json=payload)
    assert response.status_code == 422


def test_ashtakavarga_returns_500_on_service_failure(app_client, valid_payload):
    with patch.object(ashtakavarga_router.CACHE_SERVICE, "get", return_value=None), \
         patch.object(ashtakavarga_service, "charts", side_effect=RuntimeError("boom")):
        response = app_client.post("/ashtakavarga", json=valid_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating ashtakavarga."


def test_ashtakavarga_returns_expected_response_shape(app_client, valid_payload):
    response = app_client.post("/ashtakavarga", json=valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "binna" in data
    assert "samudaya" in data
    assert isinstance(data["samudaya"], list)
    assert len(data["samudaya"]) == 12
    assert isinstance(data["binna"], dict)
    assert "Sun" in data["binna"]
    assert len(data["binna"]["Sun"]) == 12
    assert "Lagna" in data["binna"]
    assert sum(data["samudaya"]) == 337
