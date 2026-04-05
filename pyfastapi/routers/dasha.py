import dataclasses
import logging
import os
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from cache_service import CacheConfig, HoroscopeCacheService
from dependencies import verify_app_check
from models import DashaResponse, HoroscopeRequest
from services import dasha_service

logger = logging.getLogger("uvicorn.error")

CACHE_SERVICE = HoroscopeCacheService(
    dataclasses.replace(
        CacheConfig.from_env(),
        key_prefix=os.getenv("DASHA_CACHE_KEY_PREFIX", "dasha:v1"),
    )
)

router = APIRouter()


@router.post("/dasha", response_model=DashaResponse)
async def get_dasha(
    data: HoroscopeRequest,
    app_check_claims=Depends(verify_app_check),
) -> DashaResponse:
    _ = app_check_claims
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
            logger.info("dasha status=success source=cache")
            return cached_payload

        payload = await run_in_threadpool(dasha_service.build_dasha_payload, data)
        CACHE_SERVICE.set(cache_key, payload)
        logger.info(
            "dasha status=success source=generated duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        return payload

    except ValueError as e:
        logger.warning("Invalid dasha input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.error("Dasha generation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error generating dasha.")
