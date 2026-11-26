import logging
from typing import Dict, List

from jhora import utils
from jhora.panchanga import drik

from config import suppress_third_party_stdout, with_engine_state
from models import PanchangaRequest

logger = logging.getLogger("uvicorn.error")


def _get_name_lists(language: str) -> Dict[str, List[str]]:
    with suppress_third_party_stdout():
        utils.set_language(language)
    names = {
        "vaara": list(utils.DAYS_LIST),
        "tithi": list(utils.TITHI_LIST),
        "nakshatra": [name.strip() for name in utils.NAKSHATRA_LIST],
        "yoga": list(utils.YOGAM_LIST),
        "karana": list(utils.KARANA_LIST),
        "lunar_month": list(utils.MONTH_LIST),
    }
    if language != "en":
        with suppress_third_party_stdout():
            utils.set_language("en")
    return names


def _jd_to_local_hhmm(jd_utc: float, tz: float) -> str:
    y, mo, d, frac_h = utils.jd_to_gregorian(jd_utc + tz / 24.0)
    h = int(frac_h)
    m = int((frac_h - h) * 60)
    return f"{h:02d}:{m:02d}"


@with_engine_state
def build_panchanga_payload(data: PanchangaRequest) -> Dict:
    year, month, day = [int(p) for p in data.date.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd = utils.julian_day_number(date_in, (hour, minute, 0))

    names = _get_name_lists(data.language)

    with suppress_third_party_stdout():
        tithi_result = drik.tithi(jd, place)
        nak_result = drik.nakshatra(jd, place)
        yoga_result = drik.yogam(jd, place)
        karana_result = drik.karana(jd, place)
        vaara_result = drik.civil_weekday(jd)
        lunar_month_result = drik.lunar_month(jd, place)
        sunrise_result = drik.sunrise(jd, place)
        sunset_result = drik.sunset(jd, place)

    def name_at(kind: str, position: int, index: int) -> str:
        options = names[kind]
        return options[position].strip() if 0 <= position < len(options) else f"{kind}{index}"

    tithi_idx = int(tithi_result[0])
    nak_idx = int(nak_result[0])
    yoga_idx = int(yoga_result[0])
    karana_idx = int(karana_result[0])
    vaara_idx = int(vaara_result)
    lunar_month_idx = int(lunar_month_result[0])

    tithi_name = name_at("tithi", tithi_idx - 1, tithi_idx)
    nak_name = name_at("nakshatra", nak_idx - 1, nak_idx)
    yoga_name = name_at("yoga", yoga_idx - 1, yoga_idx)
    karana_name = name_at("karana", karana_idx - 1, karana_idx)
    vaara_name = name_at("vaara", vaara_idx, vaara_idx)
    lunar_month_name = name_at("lunar_month", lunar_month_idx - 1, lunar_month_idx)

    sunrise_str = sunrise_result[1][:5] if len(sunrise_result[1]) >= 5 else sunrise_result[1]
    sunset_str = sunset_result[1][:5] if len(sunset_result[1]) >= 5 else sunset_result[1]

    return {
        "status": "success",
        "data": {
            "date": data.date,
            "vaara": vaara_name,
            "tithi": tithi_name,
            "tithi_index": tithi_idx,
            "nakshatra": nak_name,
            "nakshatra_index": nak_idx,
            "yoga": yoga_name,
            "yoga_index": yoga_idx,
            "karana": karana_name,
            "karana_index": karana_idx,
            "lunar_month": lunar_month_name,
            "sunrise": sunrise_str,
            "sunset": sunset_str,
        },
    }
