from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import contextlib
from jhora.horoscope.main import Horoscope
from jhora.panchanga import drik

import swisseph as swe

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins; fine for a public API
    allow_methods=["*"],
    allow_headers=["*"],
)

ephe_path = os.path.join(os.getcwd(), "jhora/data/ephe")
if not os.path.exists(ephe_path):
    print(f"WARNING: Ephemeris path not found at {ephe_path}")
swe.set_ephe_path(ephe_path)

# Define the data structure
class HoroscopeRequest(BaseModel):
    dob: str  # YYYY-MM-DD
    time: str # HH:MM
    lat: float
    lng: float
    tz: float
    language: str = "en"

@app.post("/horoscope")
async def get_horoscope(data: HoroscopeRequest):
    try:
        # Parse date
        year, month, day = [int(part) for part in data.dob.split("-")]
        
        # Silence library prints and run logic
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
                horoscope_info = horoscope.get_horoscope_information()
        
        return {
            "status": "success",
            "horoscope": horoscope_info
        }
        
    except Exception as e:
        print(f"Error processing horoscope: {e}") # This shows up in Cloud Run logs
        raise HTTPException(status_code=400, detail="Internal processing error. Check input formats.")

@app.get("/")
def health_check():
    return {"status": "online"}