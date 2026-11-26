"""Language-independent regression values (indices and numbers) for endpoints
that have no full-response benchmark, so a library upgrade cannot shift results
unnoticed.
"""
import json
from pathlib import Path

from limiter import limiter

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "calculation_benchmark_cases.json"


def _calculated_values(path, data):
    if path == "/arudha":
        return {
            "bhava": [[e["sign_index"], e["longitude_in_sign"]] for e in data["bhava_arudhas"]],
            "graha": [e["sign_index"] for e in data["graha_arudhas"]],
        }
    if path == "/yogas":
        return {yoga["name"]: yoga["present"] for yoga in data["yogas"]}
    if path == "/transit/gochar":
        fields = ("longitude", "sign", "pada", "house_from_lagna", "house_from_moon", "is_retrograde")
        return {
            "natal": [data["natal_lagna_sign"], data["natal_moon_sign"]],
            "planets": [[planet[f] for f in fields] for planet in data["transit_planets"]],
        }
    if path == "/transit/varsha":
        return {"chart_date": data["chart_date"], "occupancy": [len(house) for house in data["chart"]]}
    if path == "/panchanga":
        fields = ("tithi_index", "nakshatra_index", "yoga_index", "karana_index", "sunrise", "sunset")
        return {f: data[f] for f in fields}
    return data


def test_calculation_benchmarks_match_fixture(app_client, monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)
    for case in json.loads(FIXTURE_PATH.read_text()):
        response = app_client.post(case["path"], json=case["input"])
        assert response.status_code == 200, case
        assert _calculated_values(case["path"], response.json()["data"]) == case["expected"], case
