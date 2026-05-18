import logging
from typing import Dict

from jhora import utils
from jhora.panchanga import drik

from config import suppress_third_party_stdout
from helpers import NORTH_EN_NAKSHATRA_NAMES
from models import PanchangaRequest

logger = logging.getLogger("uvicorn.error")

_VAARA_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

_YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarman", "Dhriti", "Shula", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti",
]

_LUNAR_MONTH_NAMES = [
    "Chaitra", "Vaishakha", "Jyeshtha", "Ashadha",
    "Shravana", "Bhadrapada", "Ashvina", "Kartika",
    "Margashirsha", "Pausha", "Magha", "Phalguna",
]


def _get_name_lists(language: str, chart_style: str):
    with suppress_third_party_stdout():
        utils.set_language(language)
    tithi_names = [utils.TITHI_LIST[i] for i in range(min(30, len(utils.TITHI_LIST)))]
    nak_names = [utils.NAKSHATRA_LIST[i].strip() for i in range(min(28, len(utils.NAKSHATRA_LIST)))]
    karana_names = [utils.KARANA_LIST[i] for i in range(min(60, len(utils.KARANA_LIST)))]
    if language != "en":
        with suppress_third_party_stdout():
            utils.set_language("en")
    if chart_style == "north" and language == "en":
        nak_names = list(NORTH_EN_NAKSHATRA_NAMES)
    return tithi_names, nak_names, karana_names


def _jd_to_local_hhmm(jd_utc: float, tz: float) -> str:
    y, mo, d, frac_h = utils.jd_to_gregorian(jd_utc + tz / 24.0)
    h = int(frac_h)
    m = int((frac_h - h) * 60)
    return f"{h:02d}:{m:02d}"


def build_panchanga_payload(data: PanchangaRequest) -> Dict:
    year, month, day = [int(p) for p in data.date.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd = utils.julian_day_number(date_in, (hour, minute, 0))

    tithi_names, nak_names, karana_names = _get_name_lists(data.language, data.chart_style)

    with suppress_third_party_stdout():
        tithi_result = drik.tithi(jd, place)
        nak_result = drik.nakshatra(jd, place)
        yoga_result = drik.yogam(jd, place)
        karana_result = drik.karana(jd, place)
        vaara_result = drik.vaara(jd)
        lunar_month_result = drik.lunar_month(jd, place)
        sunrise_result = drik.sunrise(jd, place)
        sunset_result = drik.sunset(jd, place)

    tithi_idx = int(tithi_result[0])
    tithi_name = tithi_names[tithi_idx - 1] if 0 < tithi_idx <= len(tithi_names) else f"Tithi{tithi_idx}"

    nak_idx = int(nak_result[0])
    nak_name = nak_names[nak_idx - 1] if 0 < nak_idx <= len(nak_names) else f"Nakshatra{nak_idx}"

    yoga_idx = int(yoga_result[0])
    yoga_name = _YOGA_NAMES[yoga_idx - 1] if 0 < yoga_idx <= len(_YOGA_NAMES) else f"Yoga{yoga_idx}"

    karana_idx = int(karana_result[0])
    karana_name = karana_names[karana_idx - 1] if 0 < karana_idx <= len(karana_names) else f"Karana{karana_idx}"

    vaara_idx = int(vaara_result)
    vaara_name = _VAARA_NAMES[vaara_idx] if 0 <= vaara_idx < len(_VAARA_NAMES) else f"Vaara{vaara_idx}"

    lunar_month_idx = int(lunar_month_result[0])
    lunar_month_name = (
        _LUNAR_MONTH_NAMES[lunar_month_idx - 1]
        if 0 < lunar_month_idx <= len(_LUNAR_MONTH_NAMES)
        else f"Month{lunar_month_idx}"
    )

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
