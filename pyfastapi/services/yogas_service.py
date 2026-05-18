import logging
from typing import Dict

from jhora.horoscope.chart import yoga
from jhora.panchanga import drik
from jhora import utils

from config import suppress_third_party_stdout
from models import HoroscopeRequest

logger = logging.getLogger("uvicorn.error")

_YOGAS_TO_CHECK = [
    ("Ruchaka", "Mars", yoga.ruchaka_yoga_from_jd_place),
    ("Bhadra", "Mercury", yoga.bhadra_yoga_from_jd_place),
    ("Hamsa", "Jupiter", yoga.hamsa_yoga_from_jd_place),
    ("Malavya", "Venus", yoga.maalavya_yoga_from_jd_place),
    ("Shasha", "Saturn", yoga.sasa_yoga_from_jd_place),
    ("Adhi", None, yoga.adhi_yoga_from_jd_place),
    ("Kemadruma", None, yoga.kemadruma_yoga_from_jd_place),
]


def build_yogas_payload(data: HoroscopeRequest) -> Dict:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))

    results = []
    for name, planet, fn in _YOGAS_TO_CHECK:
        try:
            with suppress_third_party_stdout():
                present = bool(fn(jd_local, place))
        except Exception as e:
            logger.warning("Could not compute yoga %s: %s", name, e)
            present = False
        results.append({"name": name, "planet": planet, "present": present})

    return {
        "status": "success",
        "data": {
            "yogas": results,
        },
    }
