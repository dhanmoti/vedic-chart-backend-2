import dataclasses
import logging
import os
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from cache_service import CacheConfig, HoroscopeCacheService
from dependencies import verify_app_check
from models import PanchangaRequest, PanchangaResponse
from services import panchanga_service

logger = logging.getLogger("uvicorn.error")

CACHE_SERVICE = HoroscopeCacheService(
    dataclasses.replace(
        CacheConfig.from_env(),
        key_prefix=os.getenv("PANCHANGA_CACHE_KEY_PREFIX", "panchanga:v1"),
    )
)

router = APIRouter()


@router.post(
    "/panchanga",
    response_model=PanchangaResponse,
    summary="Panchanga (Daily Calendar)",
    description=(
        "Returns the five panchanga elements — tithi, nakshatra, yoga, karana, vaara — "
        "along with sunrise, sunset, and lunar month for the given date and location."
    ),
    dependencies=[Depends(verify_app_check)],
)
async def get_panchanga(data: PanchangaRequest) -> PanchangaResponse:
    compute_started = time.perf_counter()
    try:
        normalized_key_fields = CACHE_SERVICE.normalize_key_fields(
            dob=data.date,
            time_value=data.time,
            lat=data.lat,
            lng=data.lng,
            tz=data.tz,
            language=data.language,
        )
        normalized_key_fields["chart_style"] = data.chart_style
        cache_key = CACHE_SERVICE.build_cache_key(normalized_key_fields)
        cached_payload = CACHE_SERVICE.get(cache_key)
        if cached_payload is not None:
            logger.info("panchanga status=success source=cache")
            return cached_payload

        payload = await run_in_threadpool(panchanga_service.build_panchanga_payload, data)
        CACHE_SERVICE.set(cache_key, payload)
        logger.info(
            "panchanga status=success source=generated duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        return payload

    except ValueError as e:
        logger.warning("Invalid panchanga input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.error("Panchanga generation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error generating panchanga.")
