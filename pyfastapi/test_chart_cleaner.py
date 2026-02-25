import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers


class SharedChartCleanerTests(unittest.TestCase):
    def test_divisional_chart_keys_follow_configured_factors(self):
        raw_horoscope = (
            {"Raasi-Ascendant": "Aries 10 10 10"},
            [["Sun\nMoon"], ["Mars\nMercury"]],
            [0],
        )

        with patch.object(helpers.const, "division_chart_factors", [1, 9]):
            result = helpers.ChartCleaner.format_response(raw_horoscope)

        self.assertEqual(result["charts"].keys(), {"D1", "D9"})
        self.assertEqual(result["charts"]["D1"], [["Sun", "Moon"]])
        self.assertEqual(result["charts"]["D9"], [["Mars", "Mercury"]])

    def test_fallback_house_parsing_and_label_derivation(self):
        raw_horoscope = (
            {
                "Raasi-Ascendant": "Aries 10 10 10",
                "D9-Ascendant": "Cancer 2 2 2",
            },
            [["Sun\n\n☉Moon"], [" Mars\nMercury\n"], ["Ketu\n\n"]],
            [0],
        )

        with patch.object(helpers.const, "division_chart_factors", [1, 9]), patch.object(
            helpers.logger, "warning"
        ) as warning_mock:
            result = helpers.ChartCleaner.format_response(raw_horoscope)

        self.assertIsInstance(result["charts"], list)
        self.assertEqual(result["charts"][0]["label"], "Raasi")
        self.assertEqual(result["charts"][0]["factor"], 1)
        self.assertEqual(result["charts"][0]["houses"], [["Sun", "Moon"]])

        self.assertEqual(result["charts"][1]["label"], "D9")
        self.assertEqual(result["charts"][1]["factor"], 9)
        self.assertEqual(result["charts"][1]["houses"], [["Mars", "Mercury"]])

        self.assertEqual(result["charts"][2]["label"], "chart_3")
        self.assertIsNone(result["charts"][2]["factor"])
        self.assertEqual(result["charts"][2]["houses"], [["Ketu"]])
        warning_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
