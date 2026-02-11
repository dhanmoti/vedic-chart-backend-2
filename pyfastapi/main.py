from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, validator
from datetime import date
from typing import Dict, List, Optional
import os
import contextlib
import re
import logging
import traceback

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
logger.setLevel(logging.INFO)

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

    try:
        claims = app_check.verify_token(token)
        return claims
    except firebase_exceptions.FirebaseError as e:
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

swe.set_ephe_path(ephe_path)

# -------------------------------------------------------------------
# Helper Logic
# -------------------------------------------------------------------
class ChartCleaner:
    @staticmethod
    def clean_text(text: str) -> str:
        return (
            re.sub(r"[^\x00-\x7F]+", "", text)
            .replace("\n", " ")
            .strip()
        )

    @staticmethod
    def format_response(raw_horoscope):
        placements = {
            ChartCleaner.clean_text(k): ChartCleaner.clean_text(v)
            for k, v in raw_horoscope[0].items()
        }

        chart_labels = [f"D{factor}" for factor in const.division_chart_factors]
        formatted_charts = {}

        for idx, name in enumerate(chart_labels):
            if idx >= len(raw_horoscope[1]):
                break
            formatted_charts[name] = [
                [
                    ChartCleaner.clean_text(p)
                    for p in house.split("\n")
                    if p.strip()
                ]
                for house in raw_horoscope[1][idx]
            ]

        return {
            "placements": placements,
            "charts": formatted_charts,
            "house_indices": raw_horoscope[2],
        }

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
    try:
        year, month, day = [int(p) for p in data.dob.split("-")]
        hour, minute = [int(p) for p in data.time.split(":")]
        date_in = drik.Date(year, month, day)
        place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
        birth_julian_day = utils.julian_day_number(date_in, (hour, minute, 0))

        # Silence noisy stdout from jhora
        with open(os.devnull, "w") as fnull:
            with contextlib.redirect_stdout(fnull):
                horoscope = Horoscope(
                    latitude=data.lat,
                    longitude=data.lng,
                    timezone_offset=data.tz,
                    date_in=date_in,
                    birth_time=data.time,
                    language=data.language,
                )
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

        with open(os.devnull, "w") as fnull:
            with contextlib.redirect_stdout(fnull):
                try:
                    utils.set_language(data.language)
                    jd_utc = birth_julian_day - (place.timezone / 24.0)

                    try:
                        asc_sign, _asc_longitude, asc_nakshatra_index, asc_pada = drik.ascendant(
                            jd_utc,
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
                                rahu_longitude = drik.sidereal_longitude(jd_utc, const._RAHU)
                                longitude = (rahu_longitude + 180.0) % 360.0
                            else:
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

    except ValueError as e:
        logger.warning("Invalid input: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Invalid input parameters."
        )
    except Exception as e:
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
