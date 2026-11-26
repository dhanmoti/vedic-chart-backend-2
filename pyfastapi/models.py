import os
import re
from datetime import date, datetime
from typing import Annotated, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, Field, PrivateAttr, field_validator, model_validator
from timezonefinder import TimezoneFinder

from config import SUPPORTED_LANGUAGES

TZ_ID_DESC = (
    "Optional IANA zone ID (e.g. 'Asia/Kolkata'). When given, it takes precedence over `tz`; "
    "the UTC offset (incl. DST/historical changes) is resolved for the birth date and time."
)


def resolve_tz_offset(tz_id: str, date_str: str, time_str: str, fold: int = 0) -> float:
    """UTC offset in hours in effect in `tz_id` at the given local date/time (DST/history aware)."""
    try:
        zone = ZoneInfo(tz_id)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"unknown tz_id '{tz_id}'")
    y, m, d = [int(p) for p in date_str.split("-")]
    hh, mm = [int(p) for p in time_str.split(":")]
    offset = datetime(y, m, d, hh, mm, tzinfo=zone, fold=fold).utcoffset()
    return offset.total_seconds() / 3600.0


_TZ_FINDER: Optional[TimezoneFinder] = None


def _infer_tz_id(lat: float, lng: float) -> Optional[str]:
    global _TZ_FINDER
    if _TZ_FINDER is None:
        _TZ_FINDER = TimezoneFinder()
    zone = _TZ_FINDER.timezone_at(lat=lat, lng=lng)
    # Etc/GMT* is open ocean: no DST/history to correct
    return zone if zone and not zone.startswith("Etc/") else None


def _naive_offsets(tz_id: str) -> set:
    """Offsets a client would plausibly send today for this zone: now, and mid-winter/mid-summer of this year."""
    zone = ZoneInfo(tz_id)
    now = datetime.now(zone)
    samples = (now, datetime(now.year, 1, 1, 12, tzinfo=zone), datetime(now.year, 7, 1, 12, tzinfo=zone))
    return {sample.utcoffset().total_seconds() / 3600.0 for sample in samples}


def _auto_correct_tz(model, date_str: str, time_str: str) -> None:
    """Fix a client-sent `tz` that is just the zone's present-day offset when the birth-time offset differed
    (DST, historical changes). A `tz` that matches neither is trusted as-is."""
    if os.getenv("TZ_AUTO_CORRECT", "true").strip().lower() not in ("1", "true", "yes"):
        return
    zone = _infer_tz_id(model.lat, model.lng)
    if not zone:
        return
    # Both folds: in a repeated or skipped DST hour either offset may be what the client meant
    at_event = {resolve_tz_offset(zone, date_str, time_str, fold) for fold in (0, 1)}
    if model.tz not in at_event and model.tz in _naive_offsets(zone):
        model.tz_id = zone


def _apply_tz_id(model, date_str: str, time_str: str):
    if not model.tz_id:
        if model.tz is None:
            raise ValueError("either tz or tz_id is required")
        _auto_correct_tz(model, date_str, time_str)
    if model.tz_id:
        model.tz = resolve_tz_offset(model.tz_id, date_str, time_str)
    return model


def _supported_language(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "en"


Language = Annotated[str, AfterValidator(_supported_language)]


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
    tz: Optional[float] = None
    tz_id: Optional[str] = Field(None, description=TZ_ID_DESC)
    language: Language = "en"
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
        if value is not None and not (-14.0 <= value <= 14.0):
            raise ValueError("tz must be between -14 and 14")
        return value

    @model_validator(mode="after")
    def resolve_tz(self):
        return _apply_tz_id(self, self.dob, self.time)


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
    balance: Optional[DashaBalance] = None
    dashas: List[MahadashaEntry]
    system: str = "vimshottari"


class DashaResponse(BaseModel):
    status: str
    data: DashaData


class DashaRequest(HoroscopeRequest):
    system: Literal[
        "vimshottari",
        "ashtottari",
        "yogini",
        "kalachakra",
        "chara",
        "lagna_kendradi_rasi",
        "sudasa",
        "narayana",
        "drig",
        "shoola",
        "niryaana_shoola",
    ] = "vimshottari"


class GocharRequest(BaseModel):
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    time: str = Field(..., description="Time of birth in 24-hour format (HH:MM)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    tz: Optional[float] = Field(None, ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14). Required unless tz_id is given")
    tz_id: Optional[str] = Field(None, description=TZ_ID_DESC)
    language: Language = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English planet/nakshatra names, 'south' uses standard transliteration")
    transit_date: str = Field(..., description="Date to compute planetary positions for (YYYY-MM-DD)")
    transit_time: str = Field("12:00", description="Time of transit calculation in 24-hour format (HH:MM), defaults to noon")
    _transit_tz: Optional[float] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def resolve_tz(self):
        _apply_tz_id(self, self.dob, self.time)
        if self.tz_id:
            self._transit_tz = resolve_tz_offset(self.tz_id, self.transit_date, self.transit_time)
        return self

    @property
    def transit_tz(self) -> float:
        return self._transit_tz if self._transit_tz is not None else self.tz

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
    tz: Optional[float] = Field(None, ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14). Required unless tz_id is given")
    tz_id: Optional[str] = Field(None, description=TZ_ID_DESC)
    language: Language = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English planet names, 'south' uses standard transliteration")
    year: int = Field(..., ge=1, le=120, description="Year of life for the annual chart (e.g. 35 for the 35th year)")

    @model_validator(mode="after")
    def resolve_tz(self):
        return _apply_tz_id(self, self.dob, self.time)

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
    tz: Optional[float] = Field(None, ge=-14.0, le=14.0, description="Timezone offset in hours (-14 to 14). Required unless tz_id is given")
    tz_id: Optional[str] = Field(None, description=TZ_ID_DESC)
    language: Language = Field("en", description="Language code for output labels")
    chart_style: Literal["north", "south"] = Field("south", description="Chart style: 'north' uses Sanskrit English nakshatra names, 'south' uses standard transliteration")

    @model_validator(mode="after")
    def resolve_tz(self):
        return _apply_tz_id(self, self.date, self.time)

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


class BhavaArudhaEntry(BaseModel):
    house: int
    label: str
    sign_index: int
    sign: str
    sign_symbol: str
    longitude_in_sign: float


class GrahaArudhaEntry(BaseModel):
    planet: str
    sign_index: int
    sign: str
    sign_symbol: str


class ArudhaData(BaseModel):
    bhava_arudhas: List[BhavaArudhaEntry]
    graha_arudhas: List[GrahaArudhaEntry]


class ArudhaResponse(BaseModel):
    status: str
    data: ArudhaData
