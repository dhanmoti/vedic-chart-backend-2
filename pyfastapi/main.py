from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from datetime import date, time
import os
import contextlib
import re

# Astrological Library Imports
from jhora import const
from jhora.horoscope.main import Horoscope
from jhora.panchanga import drik
import swisseph as swe

# Firebase Admin Imports
import firebase_admin
from firebase_admin import app_check, credentials

app = FastAPI()

# --- FIREBASE INITIALIZATION ---
# Cloud Run automatically provides credentials via the environment.
# This check prevents re-initialization errors during local 'hot reloads'.
if not firebase_admin._apps:
    firebase_admin.initialize_app()

# --- APP CHECK DEPENDENCY ---
async def verify_app_check(x_firebase_appcheck: str = Header(None)):
    """
    FastAPI dependency to verify the Firebase App Check token.
    The Flutter app must send this in the 'X-Firebase-AppCheck' header.
    """
    if not x_firebase_appcheck:
        raise HTTPException(
            status_code=401, 
            detail="X-Firebase-AppCheck header is missing."
        )
    
    try:
        # verify_token returns decoded claims if successful
        app_check.verify_token(x_firebase_appcheck)
    except Exception as e:
        # Log the error internally for debugging
        print(f"App Check Verification Failed: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired App Check token."
        )

# --- CORS SETUP ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ephemeris path setup
ephe_path = os.path.join(os.getcwd(), "jhora/data/ephe")
if not os.path.exists(ephe_path):
    print(f"WARNING: Ephemeris path not found at {ephe_path}")
swe.set_ephe_path(ephe_path)

# --- HELPER LOGIC ---
class ChartCleaner:
    @staticmethod
    def clean_text(text):
        return re.sub(r'[^\x00-\x7F]+', '', text).replace('\n', ' ').strip()

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
                [ChartCleaner.clean_text(p) for p in house.split('\n') if p.strip()]
                for house in raw_horoscope[1][idx]
            ]
        return {
            "placements": placements,
            "charts": formatted_charts,
            "house_indices": raw_horoscope[2]
        }

# --- MODELS ---
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

# --- ENDPOINTS ---

# Added verify_app_check as a dependency here
@app.post("/horoscope", dependencies=[Depends(verify_app_check)])
async def get_horoscope(data: HoroscopeRequest):
    try:
        year, month, day = [int(part) for part in data.dob.split("-")]
        
        with open(os.devnull, 'w') as fnull:
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
        
    except Exception as e:
        print(f"Error processing chart: {e}")
        raise HTTPException(status_code=400, detail="Failed to generate chart.")

@app.get("/")
def health_check():
    return {"status": "online"}