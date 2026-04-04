import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main


FIXTURE_PATH = Path(__file__).resolve().parent / "horoscope_benchmark_cases.json"


class HoroscopeEndpointTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides = {}
        self.client = TestClient(main.app)
        self.valid_payload = {
            "dob": "1990-01-01",
            "time": "10:30",
            "lat": 12.9716,
            "lng": 77.5946,
            "tz": 5.5,
            "language": "en",
        }

    def tearDown(self):
        main.app.dependency_overrides = {}

    def test_horoscope_benchmark_outputs_match_fixture_for_10_variations(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        cases = json.loads(FIXTURE_PATH.read_text())
        self.assertEqual(len(cases), 10)

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                response = self.client.post("/horoscope", json=case["input"])
                self.assertEqual(response.status_code, case["status_code"])
                self.assertEqual(response.json(), case["expected"])

    def test_horoscope_requires_app_check_header(self):
        response = self.client.post("/horoscope", json=self.valid_payload)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"], "X-Firebase-AppCheck header is missing."
        )

    def test_health_check_endpoint(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "online"})

    def test_horoscope_returns_cached_payload_when_available(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

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

        with patch.object(main.CACHE_SERVICE, "normalize_key_fields", return_value={
            "dob": self.valid_payload["dob"],
            "time": self.valid_payload["time"],
            "lat": round(self.valid_payload["lat"], main.CACHE_SERVICE.config.lat_lng_precision),
            "lng": round(self.valid_payload["lng"], main.CACHE_SERVICE.config.lat_lng_precision),
            "tz": round(self.valid_payload["tz"], main.CACHE_SERVICE.config.tz_precision),
            "language": self.valid_payload["language"].strip().lower(),
        }), patch.object(main.CACHE_SERVICE, "build_cache_key", return_value="dummy_key"), patch.object(main.CACHE_SERVICE, "get", return_value=cached_payload) as mock_get:
            response = self.client.post("/horoscope", json=self.valid_payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), cached_payload)
        mock_get.assert_called_once()

    def test_horoscope_rejects_invalid_dob_format(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        payload = {**self.valid_payload, "dob": "01-01-1990"}
        response = self.client.post("/horoscope", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_horoscope_rejects_invalid_time_format(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        payload = {**self.valid_payload, "time": "24:00"}
        response = self.client.post("/horoscope", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_horoscope_rejects_missing_required_field(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        payload = {**self.valid_payload}
        payload.pop("lat")
        response = self.client.post("/horoscope", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertTrue(any(error["loc"][-1] == "lat" for error in response.json()["detail"]))

    def test_horoscope_rejects_out_of_range_coordinates(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        payload = {**self.valid_payload, "lat": 99.0, "lng": 200.0, "tz": 20.0}
        response = self.client.post("/horoscope", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertTrue(any("lat" in error["loc"] or "lng" in error["loc"] or "tz" in error["loc"] for error in response.json()["detail"]))

    def test_horoscope_returns_500_on_chart_generation_failure(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        with patch.object(main, "Horoscope") as mock_horoscope:
            mock_horoscope.side_effect = RuntimeError("boom")
            response = self.client.post("/horoscope", json=self.valid_payload)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Internal error generating chart.")


if __name__ == "__main__":
    unittest.main()
