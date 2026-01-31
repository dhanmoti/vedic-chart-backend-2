from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, validator
from datetime import date
import os
import contextlib
import re
import logging
import traceback

# --- Astrological Library Imports ---
from jhora import const
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

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.post("/horoscope")
async def get_horoscope(
    data: HoroscopeRequest,
    app_check_claims=Depends(verify_app_check),
):
    try:
        year, month, day = [int(p) for p in data.dob.split("-")]

        # Silence noisy stdout from jhora
        with open(os.devnull, "w") as fnull:
            with contextlib.redirect_stdout(fnull):
                date_in = drik.Date(year, month, day)
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
