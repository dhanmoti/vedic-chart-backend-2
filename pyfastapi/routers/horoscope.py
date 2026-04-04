import logging
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from cache_service import CacheConfig, HoroscopeCacheService
from dependencies import verify_app_check
from models import HoroscopeRequest, HoroscopeResponse
from services import horoscope_service


logger = logging.getLogger("uvicorn.error")

CACHE_SERVICE = HoroscopeCacheService(CacheConfig.from_env())

router = APIRouter()


@router.post(
    "/horoscope",
    response_model=HoroscopeResponse,
    responses={
        200: {
            "description": (
                "Generated horoscope data with divisional charts, "
                "ascendant details, and nakshatras for all supported grahas."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "placements": {
                                "Raasi-Lagna": "Aquarius",
                                "Raasi-Sun": "Capricorn",
                            },
                            "charts": {
                                "D1": [["Lagna"], ["Sun"]],
                            },
                            "house_indices": [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                            "ascendant_lord": "Saturn",
                            "ascendant_nakshatra": {
                                "name": "Shatabhisha",
                                "pada": 1,
                                "lord": "Rahu",
                            },
                            "nakshatras": {
                                "Raasi-Lagna": {
                                    "name": "Shatabhisha",
                                    "pada": 1,
                                    "lord": "Rahu",
                                },
                            },
                        },
                    }
                }
            },
        }
    },
)
async def get_horoscope(
    data: HoroscopeRequest,
    app_check_claims=Depends(verify_app_check),
) -> HoroscopeResponse:
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
            logger.info("horoscope status=success source=cache")
            logger.debug(
                "horoscope_compute status=cached duration_ms=%.2f hit_rate=%.4f",
                (time.perf_counter() - compute_started) * 1000,
                CACHE_SERVICE.metrics.snapshot()["hit_rate"],
            )
            return cached_payload

        payload = await run_in_threadpool(horoscope_service.build_horoscope_payload, data)
        CACHE_SERVICE.set(cache_key, payload)
        logger.info("horoscope status=success source=generated")
        logger.debug(
            "horoscope_compute status=success duration_ms=%.2f hit_rate=%.4f",
            (time.perf_counter() - compute_started) * 1000,
            CACHE_SERVICE.metrics.snapshot()["hit_rate"],
        )
        return payload

    except ValueError as e:
        logger.debug(
            "horoscope_compute status=failure kind=value_error duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        logger.warning("Invalid input: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input parameters.")
    except Exception as e:
        logger.debug(
            "horoscope_compute status=failure kind=internal_error duration_ms=%.2f",
            (time.perf_counter() - compute_started) * 1000,
        )
        logger.error(
            "Chart generation failed: %s\n%s",
            e,
            traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Internal error generating chart.")
