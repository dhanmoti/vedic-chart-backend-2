import logging
from typing import Dict, List

from jhora import utils
from jhora.horoscope.transit import tajaka
from jhora.panchanga import drik

from config import suppress_third_party_stdout
from helpers import ChartCleaner, NORTH_EN_PLANET_NAME_FIXES
from models import VarshaRequest

logger = logging.getLogger("uvicorn.error")


def _load_planet_names(language: str, chart_style: str) -> List[str]:
    with suppress_third_party_stdout():
        utils.set_language(language)
    names = []
    for i in range(9):
        raw = utils.PLANET_NAMES[i] if i < len(utils.PLANET_NAMES) else f"Planet{i}"
        name, _ = ChartCleaner.split_name_symbol(raw)
        names.append(ChartCleaner.clean_unicode(name))
    if language != "en":
        with suppress_third_party_stdout():
            utils.set_language("en")
    if chart_style == "north" and language == "en":
        names = [NORTH_EN_PLANET_NAME_FIXES.get(n, n) for n in names]
    return names


def _positions_to_house_chart(positions, planet_names: List[str]) -> List[List[str]]:
    houses: List[List[str]] = [[] for _ in range(12)]
    for item in positions:
        pid = item[0]
        sign_idx = int(item[1][0])
        if pid == "L":
            label = "Lagna"
        elif isinstance(pid, int) and 0 <= pid < len(planet_names):
            label = planet_names[pid]
        else:
            label = str(pid)
        houses[sign_idx].append(label)
    return houses


def build_varsha_payload(data: VarshaRequest) -> Dict:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    natal_date = drik.Date(year, month, day)
    place = drik.Place("", data.lat, data.lng, data.tz)
    jd_at_dob = utils.julian_day_number(natal_date, (hour, minute, 0))

    with suppress_third_party_stdout():
        result = tajaka.annual_chart(jd_at_dob, place, years=data.year)

    positions, chart_date_info = result
    chart_date_tuple = chart_date_info[0]
    chart_date = f"{chart_date_tuple[0]:04d}-{chart_date_tuple[1]:02d}-{chart_date_tuple[2]:02d}"

    planet_names = _load_planet_names(data.language, data.chart_style)
    house_chart = _positions_to_house_chart(positions, planet_names)

    return {
        "status": "success",
        "data": {
            "year": data.year,
            "chart_date": chart_date,
            "chart": house_chart,
        },
    }
