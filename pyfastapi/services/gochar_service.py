import logging
from typing import Dict, List

from jhora import const, utils
from jhora.horoscope.chart import charts
from jhora.panchanga import drik

from config import suppress_third_party_stdout
from helpers import ChartCleaner
from models import GocharRequest

logger = logging.getLogger("uvicorn.error")


def _load_names(language: str) -> Dict:
    with suppress_third_party_stdout():
        utils.set_language(language)

    planet_names = []
    for i in range(9):
        raw = utils.PLANET_NAMES[i] if i < len(utils.PLANET_NAMES) else f"Planet{i}"
        name, _ = ChartCleaner.split_name_symbol(raw)
        planet_names.append(ChartCleaner.clean_unicode(name))

    nak_names = [utils.NAKSHATRA_LIST[i].strip() for i in range(min(28, len(utils.NAKSHATRA_LIST)))]

    if language == "en":
        sign_names = list(const.rasi_names_en)
    else:
        sign_names = [
            ChartCleaner.strip_zodiac_prefix(utils.RAASI_LIST[i])
            for i in range(min(12, len(utils.RAASI_LIST)))
        ]
        with suppress_third_party_stdout():
            utils.set_language("en")

    return {"planet_names": planet_names, "nak_names": nak_names, "sign_names": sign_names}


def _get_natal_ref_signs(rasi_positions) -> tuple[int, int]:
    lagna_sign = 0
    moon_sign = 0
    for item in rasi_positions:
        pid = item[0]
        sign_idx = item[1][0]
        if pid == "L":
            lagna_sign = sign_idx
        elif pid == 1:
            moon_sign = sign_idx
    return lagna_sign, moon_sign


def build_gochar_payload(data: GocharRequest) -> Dict:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    natal_date = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    natal_jd_local = utils.julian_day_number(natal_date, (hour, minute, 0))

    with suppress_third_party_stdout():
        natal_rasi = charts.rasi_chart(natal_jd_local, place)

    natal_lagna_sign, natal_moon_sign = _get_natal_ref_signs(natal_rasi)

    t_year, t_month, t_day = [int(p) for p in data.transit_date.split("-")]
    t_hour, t_minute = [int(p) for p in data.transit_time.split(":")]
    transit_date = drik.Date(t_year, t_month, t_day)
    transit_jd_local = utils.julian_day_number(transit_date, (t_hour, t_minute, 0))
    transit_jd_utc = transit_jd_local - (data.tz / 24.0)

    with suppress_third_party_stdout():
        retro_set = set(drik.planets_in_retrograde(transit_jd_local, place))

    names = _load_names(data.language)

    transit_planets = []
    for planet_list_idx, planet_id in enumerate(drik.planet_list):
        try:
            if planet_id == const._KETU:
                with suppress_third_party_stdout():
                    rahu_lon = drik.sidereal_longitude(transit_jd_utc, const._RAHU)
                longitude = (rahu_lon + 180.0) % 360.0
            else:
                with suppress_third_party_stdout():
                    longitude = drik.sidereal_longitude(transit_jd_utc, planet_id)

            sign_idx = int(longitude / 30) % 12

            with suppress_third_party_stdout():
                nak_idx, pada, _ = drik.nakshatra_pada(longitude)

            nak_name = names["nak_names"][nak_idx - 1] if 0 < nak_idx <= len(names["nak_names"]) else f"Nakshatra{nak_idx}"
            is_retrograde = planet_list_idx in {7, 8} or planet_list_idx in retro_set
            house_from_lagna = (sign_idx - natal_lagna_sign) % 12 + 1
            house_from_moon = (sign_idx - natal_moon_sign) % 12 + 1

            transit_planets.append({
                "name": names["planet_names"][planet_list_idx],
                "longitude": round(longitude, 4),
                "sign": sign_idx,
                "sign_name": names["sign_names"][sign_idx],
                "nakshatra": nak_name,
                "pada": pada,
                "house_from_lagna": house_from_lagna,
                "house_from_moon": house_from_moon,
                "is_retrograde": is_retrograde,
            })
        except Exception as e:
            logger.warning("Could not compute transit planet %d: %s", planet_list_idx, e)

    return {
        "status": "success",
        "data": {
            "transit_date": data.transit_date,
            "natal_lagna_sign": natal_lagna_sign,
            "natal_moon_sign": natal_moon_sign,
            "transit_planets": transit_planets,
        },
    }
