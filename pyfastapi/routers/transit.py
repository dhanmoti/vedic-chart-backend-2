import dataclasses
import logging
import os
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from cache_service import CacheConfig, HoroscopeCacheService
from dependencies import verify_app_check
from limiter import limiter
from models import GocharRequest, GocharResponse, VarshaRequest, VarshaResponse
from services import gochar_service, varsha_service

logger = logging.getLogger("uvicorn.error")

GOCHAR_CACHE = HoroscopeCacheService(
    dataclasses.replace(
        CacheConfig.from_env(),
        key_prefix=os.getenv("GOCHAR_CACHE_KEY_PREFIX", "gochar:v1"),
    )
)

VARSHA_CACHE = HoroscopeCacheService(
    dataclasses.replace(
        CacheConfig.from_env(),
        key_prefix=os.getenv("VARSHA_CACHE_KEY_PREFIX", "varsha:v1"),
    )
)

router = APIRouter()


@router.post(
    "/transit/gochar",
    response_model=GocharResponse,
    summary="Gochar (Planetary Transits)",
    description=(
        "Returns current planetary positions at the given transit date and their "
        "house placements relative to the natal lagna and moon sign."
    ),
    dependencies=[Depends(verify_app_check)],
)
@limiter.limit(os.getenv("RATE_LIMIT_DEFAULT", "30/minute"))
async def get_gochar(request: Request, data: GocharRequest) -> GocharResponse:
    compute_started = time.perf_counter()
    try:
        normalized_key_fields = GOCHAR_CACHE.normalize_key_fields(
            dob=data.dob,
            time_value=data.time,
            lat=data.lat,
            lng=data.lng,
            tz=data.tz,
            language=data.language,
        )
        normalized_key_fields["transit_date"] = data.transit_date
        normalized_key_fields["transit_time"] = data.transit_time
        normalized_key_fields["chart_style"] = data.chart_style
        cache_key = GOCHAR_CACHE.build_cache_key(normalized_key_fields)
        cached_payload = GOCHAR_CACHE.get(cache_key)
        if cached_payload is not None:
            logger.info("gochar status=success source=cache")
            return cached_payload

        payload = await run_in_threadpool(gochar_service.build_gochar_payload, data)
        GOCHAR_CACHE.set(cache_key, payload)
        logger.info(
            "gochar status=success source=generated duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        return payload

    except ValueError as e:
        logger.warning("Invalid gochar input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.error("Gochar generation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error generating gochar.")


@router.post(
    "/transit/varsha",
    response_model=VarshaResponse,
    summary="Varsha Pravesh (Annual Chart)",
    description=(
        "Returns the Tajaka annual (solar return) chart for the given year of life."
    ),
    dependencies=[Depends(verify_app_check)],
)
@limiter.limit(os.getenv("RATE_LIMIT_DEFAULT", "30/minute"))
async def get_varsha(request: Request, data: VarshaRequest) -> VarshaResponse:
    compute_started = time.perf_counter()
    try:
        normalized_key_fields = VARSHA_CACHE.normalize_key_fields(
            dob=data.dob,
            time_value=data.time,
            lat=data.lat,
            lng=data.lng,
            tz=data.tz,
            language=data.language,
        )
        normalized_key_fields["year"] = str(data.year)
        normalized_key_fields["chart_style"] = data.chart_style
        cache_key = VARSHA_CACHE.build_cache_key(normalized_key_fields)
        cached_payload = VARSHA_CACHE.get(cache_key)
        if cached_payload is not None:
            logger.info("varsha status=success source=cache")
            return cached_payload

        payload = await run_in_threadpool(varsha_service.build_varsha_payload, data)
        VARSHA_CACHE.set(cache_key, payload)
        logger.info(
            "varsha status=success source=generated duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        return payload

    except ValueError as e:
        logger.warning("Invalid varsha input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.error("Varsha generation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error generating varsha.")
