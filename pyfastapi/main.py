from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import contextlib
import re

# Astrological Library Imports
from jhora import const
from jhora.horoscope.main import Horoscope
from jhora.panchanga import drik
import swisseph as swe

app = FastAPI()

# Enable CORS for mobile app connectivity
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
        """Removes astronomical symbols and formatting artifacts."""
        return re.sub(r'[^\x00-\x7F]+', '', text).replace('\n', ' ').strip()

    @staticmethod
    def format_response(raw_horoscope):
        """
        Transforms raw jhora output:
        raw_horoscope[0]: Dict of placements (Raasi, Navamsa, etc.)
        raw_horoscope[1]: List of planet positions for 12 houses across D-charts
        raw_horoscope[2]: House indices for specific points
        """
        # Clean placements (e.g., "Raasi-Sun" instead of "Raasi-Sun☉")
        placements = {
            ChartCleaner.clean_text(k): ChartCleaner.clean_text(v) 
            for k, v in raw_horoscope[0].items()
        }

        # Map divisional charts in the exact order used by Horoscope.get_horoscope_information().
        # That method builds D1 at index 0, then iterates const.division_chart_factors in order.
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
    dob: str    # YYYY-MM-DD
    time: str   # HH:MM
    lat: float
    lng: float
    tz: float
    language: str = "en"

# --- ENDPOINTS ---
@app.post("/horoscope")
async def get_horoscope(data: HoroscopeRequest):
    try:
        # Parse date components
        year, month, day = [int(part) for part in data.dob.split("-")]
        
        # Silence library prints and execute calculation logic
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
        
        # Clean and structure data for the mobile frontend
        cleaned_data = ChartCleaner.format_response(raw_info)
        
        return {
            "status": "success",
            "data": cleaned_data
        }
        
    except Exception as e:
        print(f"Error processing chart: {e}")
        raise HTTPException(
            status_code=400, 
            detail="Failed to generate chart. Please verify date/time format."
        )

@app.get("/")
def health_check():
    return {"status": "online"}
