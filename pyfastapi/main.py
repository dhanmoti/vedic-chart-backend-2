import config  # noqa: F401  — side-effects: ephemeris init, logging, varga_option_dict

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from routers import horoscope as horoscope_router
from routers import system as system_router
from routers import dasha as dasha_router
from routers import transit as transit_router
from routers import panchanga as panchanga_router
from routers import ashtakavarga as ashtakavarga_router
from routers import yogas as yogas_router
from routers import arudha as arudha_router


app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(horoscope_router.router)
app.include_router(system_router.router)
app.include_router(dasha_router.router)
app.include_router(transit_router.router)
app.include_router(panchanga_router.router)
app.include_router(ashtakavarga_router.router)
app.include_router(yogas_router.router)
app.include_router(arudha_router.router)
