from typing import Dict, List

from fastapi import APIRouter
from jhora import const

from models import LanguageEntry, LanguagesResponse
from routers.horoscope import CACHE_SERVICE


router = APIRouter()

_LANGUAGES: List[LanguageEntry] = [
    LanguageEntry(code=code, name=name)
    for name, code in const.available_languages.items()
]


@router.get("/")
def health_check():
    return {"status": "online"}


@router.get("/languages", response_model=LanguagesResponse)
def get_languages() -> LanguagesResponse:
    return LanguagesResponse(status="ok", data=_LANGUAGES)


@router.get("/metrics/cache")
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
