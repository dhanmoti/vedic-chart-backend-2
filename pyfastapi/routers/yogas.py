import dataclasses
import logging
import os
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from cache_service import CacheConfig, HoroscopeCacheService
from dependencies import verify_app_check
from models import HoroscopeRequest, YogasResponse
from services import yogas_service

logger = logging.getLogger("uvicorn.error")

CACHE_SERVICE = HoroscopeCacheService(
    dataclasses.replace(
        CacheConfig.from_env(),
        key_prefix=os.getenv("YOGAS_CACHE_KEY_PREFIX", "yogas:v1"),
    )
)

router = APIRouter()


@router.post(
    "/yogas",
    response_model=YogasResponse,
    summary="Planetary Yogas",
    description=(
        "Detects major planetary yogas (Panchamahapurusha and others) in the birth chart."
    ),
    dependencies=[Depends(verify_app_check)],
)
async def get_yogas(data: HoroscopeRequest) -> YogasResponse:
    compute_started = time.perf_counter()
    try:
        normalized_key_fields = CACHE_SERVICE.normalize_key_fields(
            dob=data.dob,
            time_value=data.time,
            lat=data.lat,
            lng=data.lng,
            tz=data.tz,
            language=data.language,
        )
        cache_key = CACHE_SERVICE.build_cache_key(normalized_key_fields)
        cached_payload = CACHE_SERVICE.get(cache_key)
        if cached_payload is not None:
            logger.info("yogas status=success source=cache")
            return cached_payload

        payload = await run_in_threadpool(yogas_service.build_yogas_payload, data)
        CACHE_SERVICE.set(cache_key, payload)
        logger.info(
            "yogas status=success source=generated duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        return payload

    except ValueError as e:
        logger.warning("Invalid yogas input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.error("Yogas generation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error generating yogas.")
