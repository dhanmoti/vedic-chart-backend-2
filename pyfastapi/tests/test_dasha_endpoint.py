import re
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import routers.dasha as dasha_router
import services.dasha_service as dasha_service


def test_dasha_requires_app_check_header(valid_payload):
    from main import app

    with TestClient(app) as client:
        response = client.post("/dasha", json=valid_payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "X-Firebase-AppCheck header is missing."


def test_dasha_returns_valid_response_structure(app_client, valid_payload):
    response = app_client.post("/dasha", json=valid_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "balance" in data
    assert "dashas" in data


def test_dasha_balance_is_ints(app_client, valid_payload):
    response = app_client.post("/dasha", json=valid_payload)
    balance = response.json()["data"]["balance"]

    assert isinstance(balance["years"], int)
    assert isinstance(balance["months"], int)
    assert isinstance(balance["days"], int)


def test_dasha_dates_are_iso_format(app_client, valid_payload):
    response = app_client.post("/dasha", json=valid_payload)
    dashas = response.json()["data"]["dashas"]

    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for maha in dashas:
        assert iso_pattern.match(maha["start_date"]), f"bad maha date: {maha['start_date']}"
        date.fromisoformat(maha["start_date"])
        for antar in maha["antardashas"]:
            assert iso_pattern.match(antar["start_date"]), f"bad antar date: {antar['start_date']}"
            date.fromisoformat(antar["start_date"])
            for pratyantar in antar["pratyantardashas"]:
                assert iso_pattern.match(pratyantar["start_date"]), (
                    f"bad pratyantar date: {pratyantar['start_date']}"
                )
                date.fromisoformat(pratyantar["start_date"])


def test_dasha_has_9x9x9_structure(app_client, valid_payload):
    response = app_client.post("/dasha", json=valid_payload)
    dashas = response.json()["data"]["dashas"]

    assert len(dashas) == 9
    for maha in dashas:
        assert len(maha["antardashas"]) == 9, f"maha {maha['lord']} has != 9 antardashas"
        for antar in maha["antardashas"]:
            assert len(antar["pratyantardashas"]) == 9, (
                f"antar {antar['lord']} has != 9 pratyantardashas"
            )


def test_dasha_planet_names_are_strings(app_client, valid_payload):
    response = app_client.post("/dasha", json=valid_payload)
    dashas = response.json()["data"]["dashas"]

    ascii_pattern = re.compile(r"^[A-Za-z ]+$")
    for maha in dashas:
        assert ascii_pattern.match(maha["lord"]), f"bad lord: {maha['lord']}"
        for antar in maha["antardashas"]:
            assert ascii_pattern.match(antar["lord"]), f"bad lord: {antar['lord']}"
            for pratyantar in antar["pratyantardashas"]:
                assert ascii_pattern.match(pratyantar["lord"]), f"bad lord: {pratyantar['lord']}"


def test_dasha_cache_hit(app_client, valid_payload):
    cached_payload = {
        "status": "success",
        "data": {
            "balance": {"years": 1, "months": 2, "days": 3},
            "dashas": [],
        },
    }

    with patch.object(dasha_router.CACHE_SERVICE, "get", return_value=cached_payload) as mock_get:
        response = app_client.post("/dasha", json=valid_payload)

    assert response.status_code == 200
    assert response.json() == cached_payload
    mock_get.assert_called_once()


def test_dasha_rejects_invalid_dob(app_client, valid_payload):
    payload = {**valid_payload, "dob": "01-01-1990"}
    response = app_client.post("/dasha", json=payload)
    assert response.status_code == 422


def test_dasha_rejects_invalid_time(app_client, valid_payload):
    payload = {**valid_payload, "time": "24:00"}
    response = app_client.post("/dasha", json=payload)
    assert response.status_code == 422


def test_dasha_rejects_missing_field(app_client, valid_payload):
    payload = {k: v for k, v in valid_payload.items() if k != "lat"}
    response = app_client.post("/dasha", json=payload)
    assert response.status_code == 422
    locs = [err["loc"] for err in response.json()["detail"]]
    assert any("lat" in loc for loc in locs)


def test_dasha_returns_500_on_service_failure(app_client, valid_payload):
    with patch.object(dasha_router.CACHE_SERVICE, "get", return_value=None), \
         patch.object(
             dasha_service.vimsottari,
             "vimsottari_mahadasa",
             side_effect=RuntimeError("boom"),
         ):
        response = app_client.post("/dasha", json=valid_payload)

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal error generating dasha."
