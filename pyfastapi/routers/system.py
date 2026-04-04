from typing import Dict

from fastapi import APIRouter

from routers.horoscope import CACHE_SERVICE


router = APIRouter()


@router.get("/")
def health_check():
    return {"status": "online"}


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
