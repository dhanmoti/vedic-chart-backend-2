"""Tripwire for pyjhora upgrades: run every service for every supported language
so a library change fails in CI instead of as a 500 in prod.

Several services swallow per-item errors and log a warning (planets, transit
planets, yogas), so warnings are treated as failures too.
"""
import logging

import pytest
from jhora import const

import config  # noqa: F401  ensures pyjhora settings are pinned
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


def test_calculation_settings_are_pinned():
    """pyjhora releases have changed these defaults before, silently shifting results."""
    assert const._DEFAULT_AYANAMSA_MODE == "LAHIRI"
    assert const.dhasa_year_duration_default == const.DHASA_YEAR_DURATION.MEAN_SIDEREAL_YEAR
    assert const.varga_option_dict[2] == (6, 2)
    assert DASHA_SYSTEMS["kalachakra"].extra_kwargs["dhasa_method"] == const.KALACHAKRA_TYPE.PVR_SANJAY_RATH
    assert DASHA_SYSTEMS["drig"].extra_kwargs["dhasa_method"] == const.DRIG_TYPE.PVR_PAPER


def test_divisional_karakas_rank_planets_by_their_position_in_that_chart():
    """Atma Karaka is the graha furthest advanced in its sign (Rahu counted backwards)."""
    divisions = horoscope_service.build_horoscope_payload(HoroscopeRequest(**BIRTH))["data"]["divisions"]

    for code, division in divisions.items():
        if code == "D2":
            continue
        advancement = {
            p.id: 30 - p.longitude_in_sign if p.id == 7 else p.longitude_in_sign
            for p in division.planets[:8]
        }
        atma = max(advancement, key=advancement.get)
        assert division.planets[atma].jaimini_karaka == "Atma Karaka", code
