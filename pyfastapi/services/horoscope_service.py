import logging
from typing import Dict

from jhora import const, utils
from jhora.horoscope.main import Horoscope
from jhora.horoscope.chart import charts
from jhora.panchanga import drik

from config import configure_ephemeris_path, ephe_path, suppress_third_party_stdout
from helpers import ChartCleaner
from models import HoroscopeRequest
from services.chart_service import traditional_parasara_hora_from_rasi_positions


logger = logging.getLogger("uvicorn.error")

_GRAHA_LABELS = {
    const._SUN: "Sun",
    const._MOON: "Moon",
    const._MARS: "Mars",
    const._MERCURY: "Mercury",
    const._JUPITER: "Jupiter",
    const._VENUS: "Venus",
    const._SATURN: "Saturn",
    const._RAHU: "Rahu",
    const._KETU: "Ketu",
}


def build_horoscope_payload(data: HoroscopeRequest) -> Dict[str, object]:
    """Compute horoscope data for the given birth details."""
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))

    configure_ephemeris_path(ephe_path)

    with suppress_third_party_stdout():
        horoscope = Horoscope(
            latitude=data.lat,
            longitude=data.lng,
            timezone_offset=data.tz,
            date_in=date_in,
            birth_time=data.time,
            language=data.language,
        )
    with suppress_third_party_stdout():
        raw_info = horoscope.get_horoscope_information()

    cleaned_data = ChartCleaner.format_response(raw_info)

    # Enforce Traditional Parasara D2 (Hora) regardless of pyjhora defaults.
    with suppress_third_party_stdout():
        rasi_positions = charts.rasi_chart(
            jd_local,
            place,
            calculation_type=horoscope.calculation_type,
            pravesha_type=horoscope.pravesha_type,
        )
    cleaned_data["charts"]["D2"] = traditional_parasara_hora_from_rasi_positions(rasi_positions)

    cleaned_data["ascendant_lord"] = None
    cleaned_data["ascendant_nakshatra"] = None
    cleaned_data["nakshatras"] = {
        f"Raasi-{label}": None for label in _GRAHA_LABELS.values()
    }
    cleaned_data["nakshatras"]["Raasi-Lagna"] = None

    _enrich_nakshatras(cleaned_data, jd_local, place, data.language)

    return {"status": "success", "data": cleaned_data}


def _enrich_nakshatras(
    cleaned_data: Dict,
    jd_local: float,
    place,
    language: str,
) -> None:
    """Populate ascendant and graha nakshatra fields in-place."""
    try:
        with suppress_third_party_stdout():
            utils.set_language(language)
        jd_utc = jd_local - (place.timezone / 24.0)

        _compute_ascendant_nakshatra(cleaned_data, jd_local, place)
        _compute_graha_nakshatras(cleaned_data, jd_utc)
    except Exception as e:
        logger.warning("Could not initialize nakshatra computation context: %s", e)


def _compute_ascendant_nakshatra(cleaned_data: Dict, jd_local: float, place) -> None:
    try:
        with suppress_third_party_stdout():
            asc_sign, _asc_longitude, asc_nakshatra_index, asc_pada = drik.ascendant(
                jd_local, place
            )
        asc_lord_index = int(const.house_owners[asc_sign])
        cleaned_data["ascendant_lord"] = ChartCleaner.clean_text(
            utils.PLANET_NAMES[asc_lord_index]
        )
        asc_nakshatra_name = ChartCleaner.clean_text(
            utils.NAKSHATRA_LIST[asc_nakshatra_index - 1]
        )
        asc_nakshatra_lord_index = utils.nakshathra_lord(asc_nakshatra_index)
        asc_nakshatra_lord_name = ChartCleaner.clean_text(
            utils.PLANET_NAMES[asc_nakshatra_lord_index]
        )
        nakshatra_info = {
            "name": asc_nakshatra_name,
            "pada": asc_pada,
            "lord": asc_nakshatra_lord_name,
        }
        cleaned_data["ascendant_nakshatra"] = nakshatra_info
        cleaned_data["nakshatras"]["Raasi-Lagna"] = nakshatra_info
    except Exception as e:
        logger.warning("Could not compute ascendant details: %s", e)


def _compute_graha_nakshatras(cleaned_data: Dict, jd_utc: float) -> None:
    for planet_id in drik.planet_list:
        label = f"Raasi-{_GRAHA_LABELS.get(planet_id, str(planet_id))}"
        try:
            longitude = _get_planet_longitude(jd_utc, planet_id)
            nakshatra_index, pada, _ = drik.nakshatra_pada(longitude)
            nakshatra_name = ChartCleaner.clean_text(
                utils.NAKSHATRA_LIST[nakshatra_index - 1]
            )
            nakshatra_lord_index = utils.nakshathra_lord(nakshatra_index)
            nakshatra_lord_name = ChartCleaner.clean_text(
                utils.PLANET_NAMES[nakshatra_lord_index]
            )
            cleaned_data["nakshatras"][label] = {
                "name": nakshatra_name,
                "pada": pada,
                "lord": nakshatra_lord_name,
            }
        except Exception as e:
            logger.warning("Could not compute %s nakshatra: %s", label, e)


def _get_planet_longitude(jd_utc: float, planet_id) -> float:
    """Return sidereal longitude for a planet, computing Ketu from Rahu."""
    if planet_id == const._KETU:
        with suppress_third_party_stdout():
            rahu_longitude = drik.sidereal_longitude(jd_utc, const._RAHU)
        return (rahu_longitude + 180.0) % 360.0

    with suppress_third_party_stdout():
        return drik.sidereal_longitude(jd_utc, planet_id)
