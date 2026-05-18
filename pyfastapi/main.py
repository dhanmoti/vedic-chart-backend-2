import config  # noqa: F401  — side-effects: ephemeris init, logging, varga_option_dict

from fastapi import FastAPI
from routers import horoscope as horoscope_router
from routers import system as system_router
from routers import dasha as dasha_router
from routers import transit as transit_router
from routers import panchanga as panchanga_router
from routers import ashtakavarga as ashtakavarga_router
from routers import yogas as yogas_router


app = FastAPI()

app.include_router(horoscope_router.router)
app.include_router(system_router.router)
app.include_router(dasha_router.router)
app.include_router(transit_router.router)
app.include_router(panchanga_router.router)
app.include_router(ashtakavarga_router.router)
app.include_router(yogas_router.router)
