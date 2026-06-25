from typing import Dict, List

from jhora import const, utils
from jhora.horoscope.chart import arudhas, charts
from jhora.panchanga import drik

from config import suppress_third_party_stdout
from helpers import ChartCleaner
from models import HoroscopeRequest

_GRAHA_LABELS = ["Lagna", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def _sign_names(language: str) -> List[str]:
    if language == "en":
        return list(const.rasi_names_en)
    with suppress_third_party_stdout():
        utils.set_language(language)
        names = [ChartCleaner.strip_zodiac_prefix(utils.RAASI_LIST[i]) for i in range(min(12, len(utils.RAASI_LIST)))]
        utils.set_language("en")
    return names


def build_arudha_payload(data: HoroscopeRequest) -> Dict:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))

    with suppress_third_party_stdout():
        planet_positions = charts.rasi_chart(jd_local, place)
        # bhava_arudha_longitudes uses the bhava-madhya (cusp) reflection method, which is
        # what JHora's own desktop app produces. The simpler whole-sign-counting function
        # (bhava_arudhas_from_planet_positions) disagrees near sign boundaries.
        bhava_arudha_longitudes = arudhas.bhava_arudha_longitudes(jd_local, place, arudha_base=0)
        graha_arudhas = arudhas.graha_arudhas_from_planet_positions(planet_positions)

    sign_names = _sign_names(data.language)

    bhava_entries = []
    for house_num, longitude in enumerate(bhava_arudha_longitudes, start=1):
        sign_idx = int(longitude // 30) % 12
        bhava_entries.append({
            "house": house_num,
            "label": f"A{house_num}",
            "sign_index": sign_idx,
            "sign": sign_names[sign_idx],
            "sign_symbol": const._zodiac_symbols[sign_idx],
            "longitude_in_sign": round(longitude % 30, 4),
        })

    graha_entries = [
        {
            "planet": label,
            "sign_index": int(sign_idx),
            "sign": sign_names[int(sign_idx)],
            "sign_symbol": const._zodiac_symbols[int(sign_idx)],
        }
        for label, sign_idx in zip(_GRAHA_LABELS, graha_arudhas)
    ]

    return {
        "status": "success",
        "data": {
            "bhava_arudhas": bhava_entries,
            "graha_arudhas": graha_entries,
        },
    }
