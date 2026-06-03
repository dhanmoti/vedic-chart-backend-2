from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits import parse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit


def _make_isolated_app(limit_spec: str) -> FastAPI:
    """Minimal FastAPI app with rate limiting — used to test 429 behavior in isolation."""
    _limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.post("/probe")
    @_limiter.limit(limit_spec)
    async def probe(request: Request):
        return {"ok": True}

    return app


def test_rate_limit_exceeded_returns_429():
    """After exhausting the per-IP limit the next request must return 429."""
    app = _make_isolated_app("1/minute")
    with TestClient(app, headers={"X-Forwarded-For": "1.2.3.4"}) as client:
        r1 = client.post("/probe")
        r2 = client.post("/probe")

    assert r1.status_code == 200
    assert r2.status_code == 429


def test_rate_limit_429_response_is_json():
    """429 body must be JSON with an 'error' key — not an unhandled 500."""
    app = _make_isolated_app("1/minute")
    with TestClient(app, headers={"X-Forwarded-For": "2.3.4.5"}) as client:
        client.post("/probe")
        response = client.post("/probe")

    assert response.status_code == 429
    body = response.json()
    assert "error" in body or "detail" in body


def test_exception_handler_registered_on_production_app():
    """RateLimitExceeded handler must be registered on the production FastAPI app."""
    from main import app

    registered = {exc for exc in app.exception_handlers}
    assert RateLimitExceeded in registered


def test_unthrottled_endpoints_not_decorated():
    """Health check and metrics endpoints must have no rate-limit decorator."""
    from routers import system as system_router

    paths = {route.path for route in system_router.router.routes}
    assert "/" in paths
    assert "/metrics/cache" in paths

    for route in system_router.router.routes:
        endpoint = getattr(route, "endpoint", None)
        assert not getattr(endpoint, "_rate_limiting", False), (
            f"{route.path} should not be rate-limited"
        )


def test_requests_within_limit_return_non_429(app_client, valid_payload):
    """A single request well within the default limit must not be rejected."""
    import routers.horoscope as horoscope_router

    with patch.object(
        horoscope_router.CACHE_SERVICE,
        "get",
        return_value=_MINIMAL_CACHED_PAYLOAD,
    ):
        response = app_client.post("/horoscope", json=valid_payload)

    assert response.status_code != 429


_MINIMAL_CACHED_PAYLOAD = {
    "status": "success",
    "data": {
        "meta": {"chart_style": "south", "language": "en"},
        "ascendant": {
            "sign": "Aries",
            "sign_index": 0,
            "sign_symbol": "♈",
            "longitude": 15.5,
            "longitude_in_sign": 15.5,
            "lord": "Mars",
            "lord_symbol": "♂",
            "nakshatra": {"name": "Aswini", "index": 1, "pada": 2, "lord": "Kethu", "lord_symbol": "☋"},
        },
        "planets": [],
        "charts": {},
        "house_signs": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "divisions": {},
    },
}
