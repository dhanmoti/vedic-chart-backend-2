import logging
from typing import Dict, List, Tuple

from jhora import const, utils
from jhora.horoscope.main import Horoscope
from jhora.horoscope.chart import charts
from jhora.panchanga import drik

from config import configure_ephemeris_path, ephe_path, suppress_third_party_stdout
from helpers import ChartCleaner
from models import AscendantInfo, DignityInfo, HoroscopeRequest, NakshatraInfo, PlanetInfo
from services.chart_service import traditional_parasara_hora_from_rasi_positions


logger = logging.getLogger("uvicorn.error")

_NORTH_EN_NAKSHATRA_NAMES = [
    "Ashvini", "Bharani", "Krittika", "Rohini", "Mrigashirsha",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Svati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purvashadha",
    "Uttarashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati", "Abhijit",
]

_NORTH_EN_PLANET_NAME_FIXES = {"Raagu": "Rahu", "Kethu": "Ketu"}

_DIGNITY_STATUS_MAP = {
    5: "own_sign",
    4: "exalted",
    3: "friend",
    2: "neutral",
    1: "enemy",
    0: "debilitated",
}


def _load_names(language: str, chart_style: str) -> Dict[str, List[str]]:
    """Load planet, sign, and nakshatra names for the given language and chart style.

    For north+en: applies targeted overrides — Rahu/Ketu names and Sanskrit nakshatras.
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

    if language != "en":
        with suppress_third_party_stdout():
            utils.set_language("en")

    if chart_style == "north" and language == "en":
        planet_names = [_NORTH_EN_PLANET_NAME_FIXES.get(n, n) for n in planet_names]
        nakshatra_names = list(_NORTH_EN_NAKSHATRA_NAMES)

    return {
        "planet_names": planet_names,
        "sign_names": sign_names,
        "nakshatra_names": nakshatra_names,
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


def _apply_north_en_chart_fixes(charts_data: Dict) -> Dict:
    return {
        chart_name: [
            [_NORTH_EN_PLANET_NAME_FIXES.get(p, p) for p in house]
            for house in houses
        ]
        for chart_name, houses in charts_data.items()
    }


def build_horoscope_payload(data: HoroscopeRequest) -> Dict[str, object]:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))
    jd_utc = jd_local - (data.tz / 24.0)

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

    cleaned = ChartCleaner.format_response(raw_info)

    # Enforce Traditional Parasara D2 (Hora) regardless of pyjhora defaults.
    with suppress_third_party_stdout():
        rasi_positions = charts.rasi_chart(
            jd_local,
            place,
            calculation_type=horoscope.calculation_type,
            pravesha_type=horoscope.pravesha_type,
        )
    cleaned["charts"]["D2"] = traditional_parasara_hora_from_rasi_positions(rasi_positions)

    names = _load_names(data.language, data.chart_style)
    ascendant_info, asc_sign_idx = _build_ascendant(jd_local, place, names)
    planet_list = _build_planet_list(jd_local, jd_utc, place, asc_sign_idx, names)
    house_signs = _compute_house_signs(asc_sign_idx)

    chart_data = cleaned["charts"]
    if data.chart_style == "north" and data.language == "en":
        chart_data = _apply_north_en_chart_fixes(chart_data)

    return {
        "status": "success",
        "data": {
            "meta": {
                "chart_style": data.chart_style,
                "language": data.language,
            },
            "ascendant": ascendant_info,
            "planets": planet_list,
            "charts": chart_data,
            "house_signs": house_signs,
        },
    }
