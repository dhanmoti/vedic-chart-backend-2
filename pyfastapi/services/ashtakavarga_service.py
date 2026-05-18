import logging
from typing import Dict, List

from jhora.horoscope.chart import ashtakavarga, charts
from jhora.panchanga import drik
from jhora import utils

from config import suppress_third_party_stdout
from models import HoroscopeRequest

logger = logging.getLogger("uvicorn.error")

_BINNA_LABELS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]


def _build_house_to_planet_list(rasi_positions) -> List[str]:
    house_to_planet = [""] * 12
    for item in rasi_positions:
        pid = item[0]
        sign_idx = int(item[1][0])
        label = "L" if pid == "L" else str(pid)
        if house_to_planet[sign_idx] == "":
            house_to_planet[sign_idx] = label
        else:
            house_to_planet[sign_idx] += "/" + label
    return house_to_planet


def build_ashtakavarga_payload(data: HoroscopeRequest) -> Dict:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))

    with suppress_third_party_stdout():
        rasi_positions = charts.rasi_chart(jd_local, place)

    house_to_planet_list = _build_house_to_planet_list(rasi_positions)

    with suppress_third_party_stdout():
        binna_av, samudaya_av, _ = ashtakavarga.get_ashtaka_varga(house_to_planet_list)

    binna = {
        label: [int(v) for v in binna_av[i]]
        for i, label in enumerate(_BINNA_LABELS)
        if i < len(binna_av)
    }
    samudaya = [int(v) for v in samudaya_av]

    return {
        "status": "success",
        "data": {
            "binna": binna,
            "samudaya": samudaya,
        },
    }
