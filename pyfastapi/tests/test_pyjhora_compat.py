"""Tripwire for pyjhora upgrades: run every service for every supported language
so a library change fails in CI instead of as a 500 in prod.

Several services swallow per-item errors and log a warning (planets, transit
planets, yogas), so warnings are treated as failures too.
"""
import logging

import pytest

import config  # noqa: F401  ensures pyjhora compatibility shims are applied
from models import DashaRequest, GocharRequest, HoroscopeRequest, PanchangaRequest, VarshaRequest
from services import (
    arudha_service,
    ashtakavarga_service,
    dasha_service,
    gochar_service,
    horoscope_service,
    panchanga_service,
    varsha_service,
    yogas_service,
)
from services.dasha_registry import DASHA_SYSTEMS

LANGUAGES = ["en", "hi", "ta", "te", "ka", "ml"]
BIRTH = {"dob": "1990-05-15", "time": "10:30", "lat": 28.6, "lng": 77.2, "tz": 5.5}


@pytest.fixture(autouse=True)
def _fail_on_swallowed_errors(caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        yield
    assert [r.getMessage() for r in caplog.get_records("call") if r.levelno >= logging.WARNING] == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_chart_service_survives_each_language(language):
    request = HoroscopeRequest(**BIRTH, language=language)

    horoscope = horoscope_service.build_horoscope_payload(request)["data"]
    assert len(horoscope["planets"]) == 9
    assert all(planet.jaimini_karaka for planet in horoscope["planets"][:8])
    assert all(len(division.planets) == 9 for division in horoscope["divisions"].values())

    arudha_service.build_arudha_payload(request)
    gochar = gochar_service.build_gochar_payload(
        GocharRequest(**BIRTH, language=language, transit_date="2024-01-01")
    )
    assert len(gochar["data"]["transit_planets"]) == 9
    varsha_service.build_varsha_payload(VarshaRequest(**BIRTH, language=language, year=30))
    panchanga_service.build_panchanga_payload(
        PanchangaRequest(date="2024-01-01", lat=28.6, lng=77.2, tz=5.5, language=language)
    )


def test_language_independent_services_survive():
    request = HoroscopeRequest(**BIRTH)
    ashtakavarga = ashtakavarga_service.build_ashtakavarga_payload(request)
    assert sum(ashtakavarga["data"]["samudaya"]) == 337
    yogas_service.build_yogas_payload(request)


def test_every_dasha_system_survives():
    dasha_service.build_dasha_payload(DashaRequest(**BIRTH))
    for system in DASHA_SYSTEMS:
        payload = dasha_service.build_generic_dasha_payload(DashaRequest(**BIRTH, system=system), system)
        assert payload["data"]["dashas"], system
