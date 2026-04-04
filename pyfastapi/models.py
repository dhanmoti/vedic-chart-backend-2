import re
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator


class HoroscopeRequest(BaseModel):
    dob: str
    time: str
    lat: float
    lng: float
    tz: float
    language: str = "en"

    @field_validator("dob")
    def validate_dob(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("dob must match YYYY-MM-DD format")
        date.fromisoformat(value)
        return value

    @field_validator("time")
    def validate_time(cls, value):
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("time must match HH:MM format")
        hour, minute = [int(p) for p in value.split(":")]
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("time must be between 00:00 and 23:59")
        return value

    @field_validator("lat")
    def validate_lat(cls, value):
        if not (-90.0 <= value <= 90.0):
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lng")
    def validate_lng(cls, value):
        if not (-180.0 <= value <= 180.0):
            raise ValueError("lng must be between -180 and 180")
        return value

    @field_validator("tz")
    def validate_tz(cls, value):
        if not (-14.0 <= value <= 14.0):
            raise ValueError("tz must be between -14 and 14")
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
