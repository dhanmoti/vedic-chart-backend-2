import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path so all modules resolve correctly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def bypass_app_check():
    async def _bypass():
        return {"sub": "test"}

    return _bypass


@pytest.fixture
def app_client(bypass_app_check):
    from main import app
    from dependencies import verify_app_check

    app.dependency_overrides[verify_app_check] = bypass_app_check
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = {}


@pytest.fixture
def valid_payload():
    return {
        "dob": "1990-01-01",
        "time": "10:30",
        "lat": 12.9716,
        "lng": 77.5946,
        "tz": 5.5,
        "language": "en",
        "chart_style": "south",
    }
