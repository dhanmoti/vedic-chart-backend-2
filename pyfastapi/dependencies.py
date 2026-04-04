import logging
import time
import traceback

from fastapi import Header, HTTPException

import firebase_admin
from firebase_admin import app_check
from firebase_admin import exceptions as firebase_exceptions


logger = logging.getLogger("uvicorn.error")

# -------------------------------------------------------------------
# Firebase Initialization (Cloud Run friendly)
# -------------------------------------------------------------------
if not firebase_admin._apps:
    firebase_admin.initialize_app()


# -------------------------------------------------------------------
# App Check Dependency
# -------------------------------------------------------------------
async def verify_app_check(
    token: str = Header(None, alias="X-Firebase-AppCheck"),
):
    """Verifies Firebase App Check token. Required for all protected endpoints."""
    if not token:
        raise HTTPException(
            status_code=401,
            detail="X-Firebase-AppCheck header is missing.",
        )

    verify_started = time.perf_counter()
    try:
        claims = app_check.verify_token(token)
        logger.debug(
            "app_check_verify status=success duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        return claims
    except firebase_exceptions.FirebaseError as e:
        logger.debug(
            "app_check_verify status=failure kind=firebase_error duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        logger.warning("App Check FirebaseError: %s | %s", e.code, e.message)
        raise HTTPException(status_code=401, detail="Invalid App Check token.")
    except Exception as e:
        logger.debug(
            "app_check_verify status=failure kind=unknown duration_ms=%.2f",
            (time.perf_counter() - verify_started) * 1000,
        )
        logger.error(
            "App Check Unknown Error: %s\n%s",
            repr(e),
            traceback.format_exc(),
        )
        raise HTTPException(status_code=401, detail="Invalid App Check token.")
