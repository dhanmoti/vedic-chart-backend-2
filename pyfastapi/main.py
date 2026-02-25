from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, validator
from datetime import date
from typing import Dict, List, Optional
import os
import contextlib
import re
import logging
import traceback
import time
import atexit
from cache_service import CacheConfig, HoroscopeCacheService

# --- Astrological Library Imports ---
from jhora import const
from jhora import utils
from jhora.horoscope.main import Horoscope
from jhora.panchanga import drik
import swisseph as swe

# --- Firebase Admin Imports ---
import firebase_admin
from firebase_admin import app_check
from firebase_admin import exceptions as firebase_exceptions


# -------------------------------------------------------------------
# App & Logging Setup
# -------------------------------------------------------------------
app = FastAPI()

logger = logging.getLogger("uvicorn.error")


def _resolve_log_level() -> int:
    configured_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return logging._nameToLevel.get(configured_level, logging.INFO)


logger.setLevel(_resolve_log_level())

for noisy_logger_name in ("jhora", "swisseph"):
    logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

_DEVNULL_WRITER = open(os.devnull, "w")
atexit.register(_DEVNULL_WRITER.close)
CACHE_SERVICE = HoroscopeCacheService(CacheConfig.from_env())


@contextlib.contextmanager
def suppress_third_party_stdout():
    with contextlib.redirect_stdout(_DEVNULL_WRITER):
        yield

# -------------------------------------------------------------------
# Firebase Initialization (Cloud Run friendly)
# -------------------------------------------------------------------
if not firebase_admin._apps:
    firebase_admin.initialize_app()

# -------------------------------------------------------------------
# App Check Dependency
# -------------------------------------------------------------------
async def verify_app_check(
    token: str = Header(None, alias="X-Firebase-AppCheck")
):
    """
    Verifies Firebase App Check token.
    Required for all protected endpoints.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="X-Firebase-AppCheck header is missing."
        )

    verify_started = time.perf_counter()
    try:
        claims = app_check.verify_token(token)
        logger.debug(
            "app_check_verify status=success duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        return claims
    except firebase_exceptions.FirebaseError as e:
        logger.debug(
            "app_check_verify status=failure kind=firebase_error duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        logger.warning(
            "App Check FirebaseError: %s | %s",
            e.code,
            e.message
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid App Check token."
        )
    except Exception as e:
        logger.debug(
            "app_check_verify status=failure kind=unknown duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        logger.error(
            "App Check Unknown Error: %s\n%s",
            repr(e),
            traceback.format_exc()
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid App Check token."
        )

# -------------------------------------------------------------------
# Ephemeris Path Setup (Container-safe)
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ephe_path = os.path.join(BASE_DIR, "jhora", "data", "ephe")

if not os.path.exists(ephe_path):
    logger.error("Ephemeris path not found: %s", ephe_path)
    raise RuntimeError("Swiss Ephemeris data not found")

def _configure_ephemeris_path(path: str) -> None:
    """Keep SwissEph path in sync for both swisseph and pyjhora internals."""
    normalized_path = os.path.abspath(path)
    const._EPHIMERIDE_DATA_PATH = normalized_path
    swe.set_ephe_path(normalized_path)


_configure_ephemeris_path(ephe_path)

# -------------------------------------------------------------------
# Helper Logic
# -------------------------------------------------------------------
class ChartCleaner:
    _UNICODE_SYMBOL_MAP = {
        "℞": "(Rx)",
    }
    _ALLOWED_NON_ASCII_SYMBOLS = set()

    @staticmethod
    def clean_text(text: str) -> str:
        cleaned_text = text.replace("\r\n", "\n").replace("\r", "\n")

        for unicode_symbol, replacement in ChartCleaner._UNICODE_SYMBOL_MAP.items():
            cleaned_text = cleaned_text.replace(unicode_symbol, replacement)

        cleaned_text = "".join(
            char
            for char in cleaned_text
            if char in {"\n", "\t"} or char.isprintable()
        )

        cleaned_text = "".join(
            char
            for char in cleaned_text
            if char.isascii() or char in ChartCleaner._ALLOWED_NON_ASCII_SYMBOLS
        )

        return re.sub(r"[ \t]+", " ", cleaned_text.replace("\n", " ")).strip()

    @staticmethod
    def format_response(raw_horoscope):
        placements = {
            ChartCleaner.clean_text(k): ChartCleaner.clean_text(v)
            for k, v in raw_horoscope[0].items()
        }

        chart_entries = raw_horoscope[1]
        expected_chart_count = len(const.division_chart_factors)

        if len(chart_entries) == expected_chart_count:
            chart_labels = [f"D{factor}" for factor in const.division_chart_factors]
            formatted_charts = {
                name: ChartCleaner._clean_chart_houses(chart_entries[idx])
                for idx, name in enumerate(chart_labels)
            }
        else:
            formatted_charts = ChartCleaner._format_fallback_charts(
                placements=placements,
                chart_entries=chart_entries,
                expected_chart_count=expected_chart_count,
            )

        return {
            "placements": placements,
            "charts": formatted_charts,
            "house_indices": raw_horoscope[2],
        }

    @staticmethod
    def _clean_chart_houses(chart_houses):
        return [
            [
                ChartCleaner.clean_text(p)
                for p in house.split("\n")
                if p.strip()
            ]
            for house in chart_houses
        ]

    @staticmethod
    def _derive_chart_labels_from_placements(placements: Dict[str, str]) -> List[str]:
        derived_labels = []
        seen_labels = set()

        for key in placements:
            if "-" not in key:
                continue
            prefix, suffix = key.split("-", 1)
            if suffix not in {"Ascendant", "Lagna"}:
                continue
            if prefix in seen_labels:
                continue
            seen_labels.add(prefix)
            derived_labels.append(prefix)

        return derived_labels

    @staticmethod
    def _extract_factor(label: str) -> Optional[int]:
        if label == "Raasi":
            return 1

        match = re.match(r"D(\d+)$", label)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _format_fallback_charts(
        placements: Dict[str, str],
        chart_entries,
        expected_chart_count: int,
    ) -> List[Dict[str, object]]:
        derived_labels = ChartCleaner._derive_chart_labels_from_placements(placements)
        fallback_charts = []

        for idx, chart_houses in enumerate(chart_entries):
            label = (
                derived_labels[idx]
                if idx < len(derived_labels)
                else f"chart_{idx + 1}"
            )
            fallback_charts.append(
                {
                    "factor": ChartCleaner._extract_factor(label),
                    "label": label,
                    "houses": ChartCleaner._clean_chart_houses(chart_houses),
                }
            )

        logger.warning(
            "Chart label fallback applied: expected=%d actual=%d derived_labels=%d",
            expected_chart_count,
            len(chart_entries),
            len(derived_labels),
        )
        return fallback_charts


_SIGN_TO_INDEX = {
    "Aries": 0,
    "Taurus": 1,
    "Gemini": 2,
    "Cancer": 3,
    "Leo": 4,
    "Virgo": 5,
    "Libra": 6,
    "Scorpio": 7,
    "Sagittarius": 8,
    "Capricorn": 9,
    "Aquarius": 10,
    "Pisces": 11,
}


def _parse_longitude_from_placement(placement_value: str) -> Optional[float]:
    match = re.search(
        r"\b(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)\s+(\d{1,2})\s+(\d{1,2})(?:\s+(\d{1,2}))?",
        placement_value,
    )
    if not match:
        return None

    sign_name = match.group(1)
    sign_index = _SIGN_TO_INDEX[sign_name]
    degrees = int(match.group(2))
    minutes = int(match.group(3))
    seconds = int(match.group(4) or 0)
    sign_offset = degrees + (minutes / 60.0) + (seconds / 3600.0)
    return sign_index * 30.0 + sign_offset


def _extract_longitude_map(placements: Dict[str, str]) -> Dict[str, float]:
    aliases = {
        "Raasi-Lagna": ["Raasi-Ascendant", "Raasi-Lagna"],
        "Raasi-Sun": ["Raasi-Sun"],
        "Raasi-Moon": ["Raasi-Moon"],
        "Raasi-Mars": ["Raasi-Mars"],
        "Raasi-Mercury": ["Raasi-Mercury"],
        "Raasi-Jupiter": ["Raasi-Jupiter"],
        "Raasi-Venus": ["Raasi-Venus"],
        "Raasi-Saturn": ["Raasi-Saturn"],
        "Raasi-Rahu": ["Raasi-Rahu", "Raasi-Raagu"],
        "Raasi-Ketu": ["Raasi-Ketu", "Raasi-Kethu"],
    }

    longitude_map: Dict[str, float] = {}
    for normalized_label, candidates in aliases.items():
        for candidate in candidates:
            placement_value = placements.get(candidate)
            if not placement_value:
                continue
            longitude = _parse_longitude_from_placement(placement_value)
            if longitude is not None:
                longitude_map[normalized_label] = longitude
                break

    rahu_longitude = longitude_map.get("Raasi-Rahu")
    ketu_longitude = longitude_map.get("Raasi-Ketu")
    if rahu_longitude is not None and ketu_longitude is None:
        longitude_map["Raasi-Ketu"] = (rahu_longitude + 180.0) % 360.0
    elif ketu_longitude is not None and rahu_longitude is None:
        longitude_map["Raasi-Rahu"] = (ketu_longitude + 180.0) % 360.0

    return longitude_map

# -------------------------------------------------------------------
# Request Models
# -------------------------------------------------------------------
class HoroscopeRequest(BaseModel):
    dob: str
    time: str
    lat: float
    lng: float
    tz: float
    language: str = "en"

    @validator("dob")
    def validate_dob(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("dob must match YYYY-MM-DD format")
        date.fromisoformat(value)
        return value

    @validator("time")
    def validate_time(cls, value):
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("time must match HH:MM format")
        return value


class NakshatraInfo(BaseModel):
    name: str
    pada: int
    lord: str


class HoroscopeData(BaseModel):
    placements: Dict[str, str]
    charts: Dict[str, List[List[str]]]
    house_indices: List[int]
    ascendant_lord: Optional[str]
    ascendant_nakshatra: Optional[NakshatraInfo]
    nakshatras: Dict[str, Optional[NakshatraInfo]]


class HoroscopeResponse(BaseModel):
    status: str
    data: HoroscopeData


def _build_horoscope_payload(data: HoroscopeRequest) -> Dict[str, object]:
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    jd_local = utils.julian_day_number(date_in, (hour, minute, 0))

    _configure_ephemeris_path(ephe_path)

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
    cleaned_data["ascendant_lord"] = None
    cleaned_data["ascendant_nakshatra"] = None
    graha_labels = {
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
    cleaned_data["nakshatras"] = {
        f"Raasi-{label}": None
        for label in graha_labels.values()
    }
    cleaned_data["nakshatras"]["Raasi-Lagna"] = None

    try:
        with suppress_third_party_stdout():
            utils.set_language(data.language)
        jd_utc = jd_local - (place.timezone / 24.0)

        try:
            with suppress_third_party_stdout():
                asc_sign, _asc_longitude, asc_nakshatra_index, asc_pada = drik.ascendant(
                    jd_local,
                    place,
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
            cleaned_data["ascendant_nakshatra"] = {
                "name": asc_nakshatra_name,
                "pada": asc_pada,
                "lord": asc_nakshatra_lord_name,
            }
            cleaned_data["nakshatras"]["Raasi-Lagna"] = {
                "name": asc_nakshatra_name,
                "pada": asc_pada,
                "lord": asc_nakshatra_lord_name,
            }
        except Exception as ascendant_exception:
            logger.warning(
                "Could not compute ascendant details: %s",
                ascendant_exception,
            )

        for planet_id in drik.planet_list:
            label = f"Raasi-{graha_labels.get(planet_id, str(planet_id))}"
            try:
                if planet_id == const._KETU:
                    with suppress_third_party_stdout():
                        rahu_longitude = drik.sidereal_longitude(jd_utc, const._RAHU)
                    longitude = (rahu_longitude + 180.0) % 360.0
                else:
                    with suppress_third_party_stdout():
                        longitude = drik.sidereal_longitude(jd_utc, planet_id)
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
            except Exception as planet_exception:
                logger.warning(
                    "Could not compute %s nakshatra: %s",
                    label,
                    planet_exception,
                )
    except Exception as nakshatra_exception:
        logger.warning(
            "Could not initialize nakshatra computation context: %s",
            nakshatra_exception,
        )

    return {"status": "success", "data": cleaned_data}

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.post(
    "/horoscope",
    response_model=HoroscopeResponse,
    responses={
        200: {
            "description": "Generated horoscope data with divisional charts, ascendant details, and nakshatras for all supported grahas.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "placements": {
                                "Raasi-Lagna": "Aquarius",
                                "Raasi-Sun": "Capricorn",
                            },
                            "charts": {
                                "D1": [
                                    ["Lagna"],
                                    ["Sun"],
                                ]
                            },
                            "house_indices": [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                            "ascendant_lord": "Saturn",
                            "ascendant_nakshatra": {"name": "Shatabhisha", "pada": 1, "lord": "Rahu"},
                            "nakshatras": {
                                "Raasi-Lagna": {"name": "Shatabhisha", "pada": 1, "lord": "Rahu"},
                                "Raasi-Sun": {"name": "Uttara Ashadha", "pada": 3, "lord": "Sun"},
                                "Raasi-Moon": {"name": "Shravana", "pada": 2, "lord": "Moon"},
                                "Raasi-Mars": {"name": "Chitra", "pada": 1, "lord": "Mars"},
                                "Raasi-Mercury": {"name": "Dhanishta", "pada": 4, "lord": "Mars"},
                                "Raasi-Jupiter": {"name": "Punarvasu", "pada": 2, "lord": "Jupiter"},
                                "Raasi-Venus": {"name": "Purva Ashadha", "pada": 1, "lord": "Venus"},
                                "Raasi-Saturn": {"name": "Shatabhisha", "pada": 2, "lord": "Rahu"},
                                "Raasi-Rahu": {"name": "Ashwini", "pada": 4, "lord": "Ketu"},
                                "Raasi-Ketu": {"name": "Swati", "pada": 2, "lord": "Rahu"}
                            },
                        },
                    }
                }
            },
        }
    },
)
async def get_horoscope(
    data: HoroscopeRequest,
    app_check_claims=Depends(verify_app_check),
) -> HoroscopeResponse:
    compute_started = time.perf_counter()
    try:
        _ = app_check_claims
        normalized_key_fields = CACHE_SERVICE.normalize_key_fields(
            dob=data.dob,
            time_value=data.time,
            lat=data.lat,
            lng=data.lng,
            tz=data.tz,
            language=data.language,
        )
        cache_key = CACHE_SERVICE.build_cache_key(normalized_key_fields)
        cached_payload = CACHE_SERVICE.get(cache_key)
        if cached_payload is not None:
            logger.info(
                "horoscope status=success source=cache"
            )
            logger.debug(
                "horoscope_compute status=cached duration_ms=%.2f hit_rate=%.4f",
                (time.perf_counter() - compute_started) * 1000,
                CACHE_SERVICE.metrics.snapshot()["hit_rate"],
            )
            return cached_payload

        payload = await run_in_threadpool(_build_horoscope_payload, data)
        CACHE_SERVICE.set(cache_key, payload)
        logger.info(
            "horoscope status=success source=generated"
        )
        logger.debug(
            "horoscope_compute status=success duration_ms=%.2f hit_rate=%.4f",
            (time.perf_counter() - compute_started) * 1000,
            CACHE_SERVICE.metrics.snapshot()["hit_rate"],
        )
        return payload

    except ValueError as e:
        logger.debug(
            "horoscope_compute status=failure kind=value_error duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        logger.warning("Invalid input: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Invalid input parameters."
        )
    except Exception as e:
        logger.debug(
            "horoscope_compute status=failure kind=internal_error duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        logger.error(
            "Chart generation failed: %s\n%s",
            e,
            traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal error generating chart."
        )

@app.get("/")
def health_check():
    return {"status": "online"}


@app.get("/metrics/cache")
def cache_metrics() -> Dict[str, object]:
    metrics = CACHE_SERVICE.metrics.snapshot()
    metrics.update(
        {
            "backend": CACHE_SERVICE.backend_name,
            "ttl_seconds": CACHE_SERVICE.config.ttl_seconds,
            "lat_lng_precision": CACHE_SERVICE.config.lat_lng_precision,
            "tz_precision": CACHE_SERVICE.config.tz_precision,
        }
    )
    return metrics
