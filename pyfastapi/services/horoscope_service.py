import logging
from typing import Dict, List, Tuple

from jhora import const, utils
from jhora.horoscope.chart import charts, house
from jhora.panchanga import drik

from config import configure_ephemeris_path, ephe_path, suppress_third_party_stdout
from helpers import ChartCleaner
from models import AscendantInfo, DignityInfo, DivisionChartInfo, DivisionPlanetInfo, HoroscopeRequest, NakshatraInfo, PlanetInfo
from services.chart_service import traditional_parasara_hora_from_rasi_positions


logger = logging.getLogger("uvicorn.error")

# Indexed by planet_list order: Sun=0 … Ketu=8
_PLANET_COLORS = [
    "sun_fiery_orange",       # 0 Surya
    "moon_pearl_white",       # 1 Chandra
    "mars_blood_red",         # 2 Mangal
    "mercury_emerald_green",  # 3 Budha
    "jupiter_honey_gold",     # 4 Guru
    "venus_pastel_pink",      # 5 Shukra
    "saturn_dark_indigo",     # 6 Shani
    "rahu_smoke_grey",        # 7 Rahu
    "ketu_ash_grey",          # 8 Ketu
]

_DIGNITY_STATUS_MAP = {
    5: "own_sign",
    4: "exalted",
    3: "friend",
    2: "neutral",
    1: "enemy",
    0: "debilitated",
}


def _load_names(language: str) -> Dict[str, List[str]]:
    """Load planet, sign, nakshatra, ascendant and karaka names for the language.

    Restores global language to 'en' after loading to avoid leaking state.
    """
    with suppress_third_party_stdout():
        utils.set_language(language)

    planet_names = []
    for i in range(9):
        raw = utils.PLANET_NAMES[i] if i < len(utils.PLANET_NAMES) else f"Planet{i}"
        name, _ = ChartCleaner.split_name_symbol(raw)
        planet_names.append(ChartCleaner.clean_unicode(name))

    if language == "en":
        sign_names = list(const.rasi_names_en)
    else:
        sign_names = []
        for i in range(12):
            raw = utils.RAASI_LIST[i] if i < len(utils.RAASI_LIST) else f"Sign{i}"
            sign_names.append(ChartCleaner.strip_zodiac_prefix(raw))

    nakshatra_names = []
    for i in range(28):
        if i < len(utils.NAKSHATRA_LIST):
            nakshatra_names.append(ChartCleaner.clean_unicode(utils.NAKSHATRA_LIST[i].strip()))
        else:
            nakshatra_names.append(f"Nakshatra{i + 1}")

    ascendant_name, _ = ChartCleaner.split_name_symbol(utils.resource_strings["ascendant_str"])
    karaka_names = [
        ChartCleaner.clean_unicode(utils.resource_strings[f"{key}_str"])
        for key in house.chara_karaka_names
    ]

    with suppress_third_party_stdout():
        utils.set_language("en")

    return {
        "planet_names": planet_names,
        "sign_names": sign_names,
        "nakshatra_names": nakshatra_names,
        "ascendant_name": ChartCleaner.clean_unicode(ascendant_name),
        "karaka_names": karaka_names,
    }


def _compute_dignity(planet_idx: int, sign_idx: int, longitude_in_sign: float) -> DignityInfo:
    score = int(const.house_strengths_of_planets[planet_idx][sign_idx])

    if score == 5 and planet_idx < 7:
        mt = const.moola_trikona_range_of_planets.get(planet_idx)
        if mt is not None:
            mt_sign, mt_start, mt_end = mt
            if mt_sign == sign_idx and mt_start <= longitude_in_sign <= mt_end:
                return DignityInfo(status="moolatrikona", score=score, label="Moolatrikona")

    return DignityInfo(
        status=_DIGNITY_STATUS_MAP[score],
        score=score,
        label=const.house_strength_types[score],
    )


def _compute_house(planet_sign_idx: int, asc_sign_idx: int) -> int:
    return (planet_sign_idx - asc_sign_idx) % 12 + 1


def _compute_house_signs(asc_sign_idx: int) -> List[int]:
    return [(asc_sign_idx + i) % 12 for i in range(12)]


def _build_nakshatra_info(longitude: float, names: Dict[str, List[str]]) -> NakshatraInfo:
    with suppress_third_party_stdout():
        nak_idx, pada, _ = drik.nakshatra_pada(longitude)
    idx = nak_idx - 1
    nak_name = names["nakshatra_names"][idx] if idx < len(names["nakshatra_names"]) else f"Nakshatra{nak_idx}"
    lord_planet_idx = utils.nakshathra_lord(nak_idx)
    return NakshatraInfo(
        name=nak_name,
        index=nak_idx,
        pada=pada,
        lord=names["planet_names"][lord_planet_idx],
        lord_symbol=const._planet_symbols[lord_planet_idx + 1],
    )


def _build_ascendant(
    jd_local: float, place, names: Dict[str, List[str]]
) -> Tuple[AscendantInfo, int]:
    with suppress_third_party_stdout():
        asc_sign_idx, asc_long_in_sign, nak_idx, pada = drik.ascendant(jd_local, place)

    asc_longitude = asc_sign_idx * 30.0 + asc_long_in_sign
    lord_planet_idx = int(const.house_owners[asc_sign_idx])

    nak_idx_0 = nak_idx - 1
    nak_name = names["nakshatra_names"][nak_idx_0] if nak_idx_0 < len(names["nakshatra_names"]) else f"Nakshatra{nak_idx}"
    nak_lord_idx = utils.nakshathra_lord(nak_idx)

    nakshatra = NakshatraInfo(
        name=nak_name,
        index=nak_idx,
        pada=pada,
        lord=names["planet_names"][nak_lord_idx],
        lord_symbol=const._planet_symbols[nak_lord_idx + 1],
    )
    asc_info = AscendantInfo(
        sign=names["sign_names"][asc_sign_idx],
        sign_index=asc_sign_idx,
        sign_symbol=const._zodiac_symbols[asc_sign_idx],
        longitude=round(asc_longitude, 4),
        longitude_in_sign=round(asc_long_in_sign, 4),
        lord=names["planet_names"][lord_planet_idx],
        lord_symbol=const._planet_symbols[lord_planet_idx + 1],
        nakshatra=nakshatra,
    )
    return asc_info, int(asc_sign_idx)


def _get_planet_longitude(jd_utc: float, planet_id) -> float:
    if planet_id == const._KETU:
        with suppress_third_party_stdout():
            rahu_longitude = drik.sidereal_longitude(jd_utc, const._RAHU)
        return (rahu_longitude + 180.0) % 360.0
    with suppress_third_party_stdout():
        return drik.sidereal_longitude(jd_utc, planet_id)


def _build_planet_list(
    jd_local: float,
    jd_utc: float,
    place,
    asc_sign_idx: int,
    names: Dict[str, List[str]],
) -> List[PlanetInfo]:
    with suppress_third_party_stdout():
        retro_set = set(drik.planets_in_retrograde(jd_local, place))
    with suppress_third_party_stdout():
        speed_info = drik.planets_speed_info(jd_local, place)

    planets = []
    for planet_list_idx, planet_id in enumerate(drik.planet_list):
        try:
            longitude = _get_planet_longitude(jd_utc, planet_id)
            sign_idx = int(longitude / 30) % 12
            long_in_sign = longitude % 30

            is_retrograde = planet_list_idx in {7, 8} or planet_list_idx in retro_set

            raw_speed = speed_info.get(planet_list_idx, [])
            daily_motion = round(abs(raw_speed[3]), 6) if len(raw_speed) > 3 else 0.0

            dignity = _compute_dignity(planet_list_idx, sign_idx, long_in_sign)
            nakshatra = _build_nakshatra_info(longitude, names)

            planets.append(PlanetInfo(
                id=planet_list_idx,
                name=names["planet_names"][planet_list_idx],
                symbol=const._planet_symbols[planet_list_idx + 1],
                color=_PLANET_COLORS[planet_list_idx],
                sign=names["sign_names"][sign_idx],
                sign_index=sign_idx,
                sign_symbol=const._zodiac_symbols[sign_idx],
                house=_compute_house(sign_idx, asc_sign_idx),
                longitude=round(longitude, 4),
                longitude_in_sign=round(long_in_sign, 4),
                is_retrograde=is_retrograde,
                daily_motion=daily_motion,
                dignity=dignity,
                nakshatra=nakshatra,
            ))
        except Exception as e:
            logger.warning("Could not compute planet %d: %s", planet_list_idx, e)

    return planets


def _chart_positions(jd_local: float, place, factor: int) -> List:
    """[[planet, (sign_index, longitude_in_sign)], ...] for the ascendant ("L") and the nine grahas."""
    with suppress_third_party_stdout():
        positions = charts.divisional_chart(
            jd_local, place, divisional_chart_factor=factor, exclude_non_planets=True
        )
    return [entry for entry in positions if entry[0] == const._ascendant_symbol or entry[0] <= const.KETU_ID]


def _jaimini_karakas(positions: List, names: Dict[str, List[str]]) -> Dict[int, str]:
    ranked_planets = house.chara_karakas(positions)
    return {planet: names["karaka_names"][rank] for rank, planet in enumerate(ranked_planets)}


def _chart_houses(positions: List, names: Dict[str, List[str]]) -> List[List[str]]:
    houses: List[List[str]] = [[] for _ in range(12)]
    for planet, (sign_idx, _) in positions:
        is_ascendant = planet == const._ascendant_symbol
        houses[sign_idx].append(names["ascendant_name"] if is_ascendant else names["planet_names"][planet])
    return houses


def _division_info(
    positions: List, planet_list: List[PlanetInfo], names: Dict[str, List[str]]
) -> DivisionChartInfo:
    placements = dict(positions)
    lagna_sign = placements[const._ascendant_symbol][0]
    karakas = _jaimini_karakas(positions, names)
    planets = []
    for p in planet_list:
        sign_idx, long_in_sign = placements[p.id]
        planets.append(DivisionPlanetInfo(
            id=p.id,
            name=p.name,
            symbol=p.symbol,
            sign=names["sign_names"][sign_idx],
            sign_index=sign_idx,
            sign_symbol=const._zodiac_symbols[sign_idx],
            longitude_in_sign=round(long_in_sign, 4),
            house=(sign_idx - lagna_sign) % 12 + 1,
            jaimini_karaka=karakas.get(p.id),
        ))
    return DivisionChartInfo(planets=planets)


def _hora_division_info(
    d2_chart: List[List[str]], planet_list: List[PlanetInfo], names: Dict[str, List[str]]
) -> DivisionChartInfo:
    name_to_sign: Dict[str, int] = {
        name: sign_idx
        for sign_idx, names_in_sign in enumerate(d2_chart)
        for name in names_in_sign
    }
    lagna_sign = name_to_sign["Ascendant"]
    planets = []
    for p in planet_list:
        sign_idx = name_to_sign[names["planet_names"][p.id]]
        planets.append(DivisionPlanetInfo(
            id=p.id,
            name=p.name,
            symbol=p.symbol,
            sign=names["sign_names"][sign_idx],
            sign_index=sign_idx,
            sign_symbol=const._zodiac_symbols[sign_idx],
            longitude_in_sign=round((p.longitude_in_sign * 2) % 30, 4),
            house=(sign_idx - lagna_sign) % 12 + 1,
        ))
    return DivisionChartInfo(planets=planets)


def _build_charts_and_divisions(
    jd_local: float, place, planet_list: List[PlanetInfo], names: Dict[str, List[str]]
) -> Tuple[Dict[str, List[List[str]]], Dict[str, DivisionChartInfo]]:
    rasi_positions = _chart_positions(jd_local, place, 1)
    rasi_karakas = _jaimini_karakas(rasi_positions, names)
    for planet_info in planet_list:
        planet_info.jaimini_karaka = rasi_karakas.get(planet_info.id)

    chart_data: Dict[str, List[List[str]]] = {}
    divisions: Dict[str, DivisionChartInfo] = {}
    for factor in const.division_chart_factors:
        code = f"D{factor}"
        if factor == 1:
            chart_data[code] = _chart_houses(rasi_positions, names)
        elif factor == 2:
            # D2 is always Traditional Parasara, regardless of pyjhora defaults.
            chart_data[code] = traditional_parasara_hora_from_rasi_positions(rasi_positions, names["planet_names"])
            divisions[code] = _hora_division_info(chart_data[code], planet_list, names)
        else:
            positions = _chart_positions(jd_local, place, factor)
            chart_data[code] = _chart_houses(positions, names)
            divisions[code] = _division_info(positions, planet_list, names)

    return chart_data, divisions


def build_horoscope_payload(data: HoroscopeRequest) -> Dict[str, object]:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))
    jd_utc = jd_local - (data.tz / 24.0)

    configure_ephemeris_path(ephe_path)

    names = _load_names(data.language)
    ascendant_info, asc_sign_idx = _build_ascendant(jd_local, place, names)
    planet_list = _build_planet_list(jd_local, jd_utc, place, asc_sign_idx, names)
    house_signs = _compute_house_signs(asc_sign_idx)
    chart_data, divisions = _build_charts_and_divisions(jd_local, place, planet_list, names)

    return {
        "status": "success",
        "data": {
            "meta": {
                "chart_style": data.chart_style,
                "language": data.language,
                **({"tz_id": data.tz_id, "tz_offset": f"{data.tz:g}"} if data.tz_id else {}),
            },
            "ascendant": ascendant_info,
            "planets": planet_list,
            "charts": chart_data,
            "house_signs": house_signs,
            "divisions": divisions,
        },
    }
