"""Tripwire for pyjhora upgrades: run every service for every supported language
so a library change fails in CI instead of as a 500 in prod.

Several services swallow per-item errors and log a warning (planets, transit
planets, yogas), so warnings are treated as failures too.
"""
import logging
import threading

import pytest
import swisseph as swe
from jhora import const

import config  # ensures pyjhora settings are pinned
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
    assert config.AYANAMSA_MODE == "LAHIRI"
    assert const.dhasa_year_duration_default == const.DHASA_YEAR_DURATION.MEAN_SIDEREAL_YEAR
    assert const.varga_option_dict[2] == (6, 2)
    # PVR book methods (project decision 2026-11-26).
    assert DASHA_SYSTEMS["kalachakra"].extra_kwargs["dhasa_method"] == const.KALACHAKRA_TYPE.PVR_SANJAY_RATH
    assert DASHA_SYSTEMS["drig"].extra_kwargs["dhasa_method"] == const.DRIG_TYPE.PVR_BOOK
    assert DASHA_SYSTEMS["sudasa"].extra_kwargs["dhasa_method"] == const.SUDASA_METHOD.PVR_BOOK
    assert DASHA_SYSTEMS["narayana"].extra_kwargs["dhasa_method"] == const.NARAYANA_OPTION.PVR_BOOK


# Swiss Ephemeris, Lahiri: sidereal Sun for 1991-11-13 15:00 UTC+8 is 206.6557 deg.
# Ref: PVR, Vedic Astrology: An Integrated Approach §1.3.13 (Chitrapaksha/Lahiri).
LAHIRI_CHECK = {"dob": "1991-11-13", "time": "15:00", "lat": 1.11, "lng": 89.88, "tz": 8.0}
LAHIRI_SUN = 206.6557
ARC_SECOND = 1 / 3600


def test_worker_thread_computes_with_lahiri():
    """Swiss Ephemeris state is thread-local; a fresh thread must still get Lahiri."""
    result = {}

    def run():
        payload = horoscope_service.build_horoscope_payload(HoroscopeRequest(**LAHIRI_CHECK))
        result["sun"] = payload["data"]["planets"][0].longitude
        result["ayanamsa"] = swe.get_ayanamsa_ut(swe.julday(1991, 11, 13, 7.0))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    assert result["ayanamsa"] == pytest.approx(swe.get_ayanamsa_ut(swe.julday(1991, 11, 13, 7.0)), abs=ARC_SECOND)
    assert result["sun"] == pytest.approx(LAHIRI_SUN, abs=ARC_SECOND)


def test_divisional_karakas_are_the_rasi_karakas():
    """Ref: PVR §7.3.6 and §8.2 - karakas come from the rasi chart and are used in every varga."""
    data = horoscope_service.build_horoscope_payload(HoroscopeRequest(**BIRTH))["data"]
    rasi_karakas = {p.id: p.jaimini_karaka for p in data["planets"]}

    advancement = {
        p.id: 30 - p.longitude_in_sign if p.id == 7 else p.longitude_in_sign
        for p in data["planets"][:8]
    }
    assert rasi_karakas[max(advancement, key=advancement.get)] == "Atma Karaka"
    assert rasi_karakas[min(advancement, key=advancement.get)] == "Dara Karaka"
    for code, division in data["divisions"].items():
        assert {p.id: p.jaimini_karaka for p in division.planets} == rasi_karakas, code


def test_karaka_labels_follow_bphs():
    """Ref: BPHS 32.13-17 and PVR §8.2 Table 13: the 4th is Matri (mother), the 8th Dara (spouse)."""
    labels = horoscope_service._load_names("en")["karaka_names"]
    assert labels == [
        "Atma Karaka", "Amatya Karaka", "Bhratri Karaka", "Matri Karaka",
        "Pitri Karaka", "Putra Karaka", "Jnaati Karaka", "Dara Karaka",
    ]
    for language in LANGUAGES:
        assert len(horoscope_service._load_names(language)["karaka_names"]) == 8


def _mahadasha_years(dashas, years_per_day):
    starts = [dasha_service._date_tuple_to_jd((*map(int, d["start_date"].split("-")), 0.0)) for d in dashas]
    return [round((b - a) * years_per_day) for a, b in zip(starts, starts[1:])]


@pytest.mark.parametrize("system", ["sudasa", "lagna_kendradi_rasi"])
def test_narayana_family_dasas_have_a_second_cycle(system):
    """Ref: PVR §18.2 note 2, §19.2(6), §20.2(6): second-cycle period = 12 - first-cycle period."""
    dashas = dasha_service.build_generic_dasha_payload(DashaRequest(**BIRTH, system=system), system)["data"]["dashas"]
    assert len(dashas) == 24
    assert [d["lord"] for d in dashas[:12]] == [d["lord"] for d in dashas[12:]]
    years = _mahadasha_years(dashas, 1 / const.sidereal_year)
    for first, second in zip(years[1:11], years[13:23]):
        assert first + second == 12


def test_second_cycle_matches_pyjhora_narayana():
    """The generic second cycle reproduces PyJHora's own Narayana second cycle."""
    from jhora.horoscope.dhasa.raasi import narayana

    date_in, tob, place = dasha_service._resolve_birth(HoroscopeRequest(**BIRTH))
    rows = narayana.narayana_dhasa_for_rasi_chart(date_in, tob, place, dhasa_level_index=3)
    first_cycle = rows[: len(rows) // 2]
    rebuilt = dasha_service._append_second_cycle(first_cycle, place, narayana)

    assert [r[0] for r in rebuilt] == [r[0] for r in rows]
    for ours, theirs in zip(rebuilt, rows):
        assert dasha_service._date_tuple_to_jd(ours[1]) == pytest.approx(
            dasha_service._date_tuple_to_jd(theirs[1]), abs=1 / 24
        )
