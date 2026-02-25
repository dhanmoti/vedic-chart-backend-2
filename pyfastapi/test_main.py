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

        payload = {**self.valid_payload, "time": "7:70"}
        response = self.client.post("/horoscope", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_horoscope_returns_500_on_chart_generation_failure(self):
        async def bypass_app_check():
            return {"sub": "test"}

        main.app.dependency_overrides[main.verify_app_check] = bypass_app_check

        with patch.object(main, "Horoscope") as mock_horoscope:
            mock_horoscope.side_effect = RuntimeError("boom")
            response = self.client.post("/horoscope", json=self.valid_payload)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Internal error generating chart.")


class ChartCleanerFormatResponseTests(unittest.TestCase):
    def test_format_response_uses_standard_label_mapping_when_lengths_match(self):
        raw_horoscope = (
            {"Raasi-Ascendant": "Aries 10 10 10"},
            [["Sun\nMoon"], ["Mars\nMercury"]],
            [0],
        )

        with patch.object(main.const, "division_chart_factors", [1, 9]):
            result = main.ChartCleaner.format_response(raw_horoscope)

        self.assertEqual(result["charts"].keys(), {"D1", "D9"})
        self.assertEqual(result["charts"]["D1"], [["Sun", "Moon"]])
        self.assertEqual(result["charts"]["D9"], [["Mars", "Mercury"]])

    def test_format_response_fallback_handles_fewer_charts_than_expected(self):
        raw_horoscope = (
            {
                "Raasi-Ascendant": "Aries 10 10 10",
                "D9-Ascendant": "Cancer 2 2 2",
            },
            [["Sun"], ["Moon"]],
            [0],
        )

        with patch.object(main.const, "division_chart_factors", [1, 2, 3]), patch.object(
            main.logger, "warning"
        ) as warning_mock:
            result = main.ChartCleaner.format_response(raw_horoscope)

        self.assertIsInstance(result["charts"], list)
        self.assertEqual(result["charts"][0]["label"], "Raasi")
        self.assertEqual(result["charts"][0]["factor"], 1)
        self.assertEqual(result["charts"][1]["label"], "D9")
        self.assertEqual(result["charts"][1]["factor"], 9)
        warning_mock.assert_called_once()

    def test_format_response_fallback_handles_extra_custom_charts(self):
        raw_horoscope = (
            {
                "Raasi-Ascendant": "Aries 10 10 10",
                "D9-Ascendant": "Cancer 2 2 2",
            },
            [["Sun"], ["Moon"], ["Ketu"]],
            [0],
        )

        with patch.object(main.const, "division_chart_factors", [1, 9]), patch.object(
            main.logger, "warning"
        ) as warning_mock:
            result = main.ChartCleaner.format_response(raw_horoscope)

        self.assertEqual(len(result["charts"]), 3)
        self.assertEqual(result["charts"][2]["label"], "chart_3")
        self.assertIsNone(result["charts"][2]["factor"])
        self.assertEqual(result["charts"][2]["houses"], [["Ketu"]])
        warning_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
