from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.arudha as arudha_router
import services.arudha_service as arudha_service


def test_arudha_requires_app_check_header(valid_payload):
    from main import app
    with TestClient(app) as client:
        response = client.post("/arudha", json=valid_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_arudha_returns_cached_payload_when_available(app_client, valid_payload):
    cached = {
        "status": "success",
        "data": {
            "bhava_arudhas": [
                {"house": 1, "label": "A1", "sign_index": 0, "sign": "Aries", "sign_symbol": "♈︎", "longitude_in_sign": 12.5},
            ],
            "graha_arudhas": [
                {"planet": "Lagna", "sign_index": 0, "sign": "Aries", "sign_symbol": "♈︎"},
            ],
        },
    }
    with patch.object(arudha_router.CACHE_SERVICE, "get", return_value=cached) as mock_get:
        response = app_client.post("/arudha", json=valid_payload)
    assert response.status_code == 200
    assert response.json() == cached
    mock_get.assert_called_once()


def test_arudha_rejects_missing_required_field(app_client, valid_payload):
    payload = {k: v for k, v in valid_payload.items() if k != "dob"}
    response = app_client.post("/arudha", json=payload)
    assert response.status_code == 422
    locs = [err["loc"] for err in response.json()["detail"]]
    assert any("dob" in loc for loc in locs)


def test_arudha_rejects_out_of_range_inputs(app_client, valid_payload):
    payload = {**valid_payload, "lng": 999.0}
    response = app_client.post("/arudha", json=payload)
    assert response.status_code == 422


def test_arudha_returns_500_on_service_failure(app_client, valid_payload):
    with patch.object(arudha_router.CACHE_SERVICE, "get", return_value=None), \
         patch.object(arudha_service.drik, "Place", side_effect=RuntimeError("boom")):
        response = app_client.post("/arudha", json=valid_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating arudha."


def test_arudha_returns_expected_response_shape(app_client, valid_payload):
    response = app_client.post("/arudha", json=valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]

    bhava_arudhas = data["bhava_arudhas"]
    assert len(bhava_arudhas) == 12
    a1 = bhava_arudhas[0]
    assert a1["house"] == 1
    assert a1["label"] == "A1"
    assert 0 <= a1["sign_index"] <= 11
    assert 0 <= a1["longitude_in_sign"] < 30

    graha_arudhas = data["graha_arudhas"]
    assert len(graha_arudhas) == 10
    assert graha_arudhas[0]["planet"] == "Lagna"
    planet_names = [g["planet"] for g in graha_arudhas]
    assert "Ketu" in planet_names
