import re
from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator


class HoroscopeRequest(BaseModel):
    dob: str
    time: str
    lat: float
    lng: float
    tz: float
    language: str = "en"
    chart_style: Literal["north", "south"] = "south"

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
    index: int
    pada: int
    lord: str
    lord_symbol: str


class DignityInfo(BaseModel):
    status: str
    score: int
    label: str


class PlanetInfo(BaseModel):
    id: int
    name: str
    symbol: str
    color: str
    sign: str
    sign_index: int
    sign_symbol: str
    house: int
    longitude: float
    longitude_in_sign: float
    is_retrograde: bool
    daily_motion: float
    dignity: DignityInfo
    nakshatra: NakshatraInfo


class AscendantInfo(BaseModel):
    sign: str
    sign_index: int
    sign_symbol: str
    longitude: float
    longitude_in_sign: float
    lord: str
    lord_symbol: str
    nakshatra: NakshatraInfo


class HoroscopeData(BaseModel):
    meta: Dict[str, str]
    ascendant: AscendantInfo
    planets: List[PlanetInfo]
    charts: Dict[str, List[List[str]]]
    house_signs: List[int]


class HoroscopeResponse(BaseModel):
    status: str
    data: HoroscopeData


class PratyantardashaEntry(BaseModel):
    lord: str
    start_date: str


class AntardashaEntry(BaseModel):
    lord: str
    start_date: str
    pratyantardashas: List[PratyantardashaEntry]


class MahadashaEntry(BaseModel):
    lord: str
    start_date: str
    antardashas: List[AntardashaEntry]


class DashaBalance(BaseModel):
    years: int
    months: int
    days: int


class DashaData(BaseModel):
    balance: DashaBalance
    dashas: List[MahadashaEntry]


class DashaResponse(BaseModel):
    status: str
    data: DashaData
