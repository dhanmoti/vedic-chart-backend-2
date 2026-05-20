import re
from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class LanguageEntry(BaseModel):
    code: str
    name: str


class LanguagesResponse(BaseModel):
    status: str
    data: List[LanguageEntry]


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
    jaimini_karaka: Optional[str] = None


class AscendantInfo(BaseModel):
    sign: str
    sign_index: int
    sign_symbol: str
    longitude: float
    longitude_in_sign: float
    lord: str
    lord_symbol: str
    nakshatra: NakshatraInfo


class DivisionPlanetInfo(BaseModel):
    id: int
    name: str
    symbol: str
    sign: str
    sign_index: int
    sign_symbol: str
    longitude_in_sign: float
    house: int
    jaimini_karaka: Optional[str] = None


class DivisionChartInfo(BaseModel):
    planets: List[DivisionPlanetInfo]


class HoroscopeData(BaseModel):
    meta: Dict[str, str]
    ascendant: AscendantInfo
    planets: List[PlanetInfo]
    charts: Dict[str, List[List[str]]]
    house_signs: List[int]
    divisions: Dict[str, DivisionChartInfo]


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


class GocharRequest(BaseModel):
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    time: str = Field(..., description="Time of birth in 24-hour format (HH:MM)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    tz: float = Field(..., ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14)")
    language: str = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English planet/nakshatra names, 'south' uses standard transliteration")
    transit_date: str = Field(..., description="Date to compute planetary positions for (YYYY-MM-DD)")
    transit_time: str = Field("12:00", description="Time of transit calculation in 24-hour format (HH:MM), defaults to noon")

    @field_validator("dob", "transit_date")
    def validate_date_format(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must match YYYY-MM-DD format")
        date.fromisoformat(value)
        return value

    @field_validator("time", "transit_time")
    def validate_time_format(cls, value):
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("time must match HH:MM format")
        hour, minute = [int(p) for p in value.split(":")]
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("time must be between 00:00 and 23:59")
        return value


class TransitPlanetInfo(BaseModel):
    name: str
    longitude: float
    sign: int
    sign_name: str
    nakshatra: str
    pada: int
    house_from_lagna: int
    house_from_moon: int
    is_retrograde: bool


class GocharData(BaseModel):
    transit_date: str
    natal_lagna_sign: int
    natal_moon_sign: int
    transit_planets: List[TransitPlanetInfo]


class GocharResponse(BaseModel):
    status: str
    data: GocharData


class VarshaRequest(BaseModel):
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    time: str = Field(..., description="Time of birth in 24-hour format (HH:MM)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    tz: float = Field(..., ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14)")
    language: str = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English planet names, 'south' uses standard transliteration")
    year: int = Field(..., ge=1, le=120, description="Year of life for the annual chart (e.g. 35 for the 35th year)")

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


class VarshaData(BaseModel):
    year: int
    chart_date: str
    chart: List[List[str]]


class VarshaResponse(BaseModel):
    status: str
    data: VarshaData


class PanchangaRequest(BaseModel):
    date: str = Field(..., description="Date for panchanga calculation (YYYY-MM-DD)")
    time: str = Field("06:00", description="Time of day in 24-hour format (HH:MM), defaults to 06:00")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    tz: float = Field(..., ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14)")
    language: str = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English nakshatra names, 'south' uses standard transliteration")

    @field_validator("date")
    def validate_date(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must match YYYY-MM-DD format")
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


class PanchangaData(BaseModel):
    date: str
    vaara: str
    tithi: str
    tithi_index: int
    nakshatra: str
    nakshatra_index: int
    yoga: str
    yoga_index: int
    karana: str
    karana_index: int
    lunar_month: str
    sunrise: str
    sunset: str


class PanchangaResponse(BaseModel):
    status: str
    data: PanchangaData


class AshtakavargaData(BaseModel):
    binna: Dict[str, List[int]]
    samudaya: List[int]


class AshtakavargaResponse(BaseModel):
    status: str
    data: AshtakavargaData


class YogaResult(BaseModel):
    name: str
    planet: Optional[str]
    present: bool


class YogasData(BaseModel):
    yogas: List[YogaResult]


class YogasResponse(BaseModel):
    status: str
    data: YogasData
