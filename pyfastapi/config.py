import atexit
import contextlib
import logging
import os

from jhora import const
import swisseph as swe


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logger = logging.getLogger("uvicorn.error")


def resolve_log_level() -> int:
    configured_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return logging._nameToLevel.get(configured_level, logging.INFO)


logger.setLevel(resolve_log_level())

for _noisy_logger in ("jhora", "swisseph"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

# -------------------------------------------------------------------
# stdout suppression (prevents third-party libraries printing to console)
# -------------------------------------------------------------------
_DEVNULL_WRITER = open(os.devnull, "w")
atexit.register(_DEVNULL_WRITER.close)


@contextlib.contextmanager
def suppress_third_party_stdout():
    with contextlib.redirect_stdout(_DEVNULL_WRITER):
        yield


# -------------------------------------------------------------------
# Ephemeris
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ephe_path = os.path.join(BASE_DIR, "jhora", "data", "ephe")

if not os.path.exists(ephe_path):
    logger.error("Ephemeris path not found: %s", ephe_path)
    raise RuntimeError("Swiss Ephemeris data not found")


def configure_ephemeris_path(path: str) -> None:
    """Keep SwissEph path in sync for both swisseph and pyjhora internals."""
    normalized_path = os.path.abspath(path)
    const._EPHIMERIDE_DATA_PATH = normalized_path
    swe.set_ephe_path(normalized_path)


configure_ephemeris_path(ephe_path)

# Use Traditional Parasara as the default Hora (D2) computation method.
# PyJHora varga option tuple format: (number_of_options, default_option).
const.varga_option_dict[2] = (6, 2)

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
_SIGN_TO_INDEX = {
    "Aries": 0,
    "Taurus": 1,
    "Gemini": 2,
    "Cancer": 3,
    "Leo": 4,
    "Virgo": 5,
    "Libra": 6,
    "Scorpio": 7,
    "Sagittarius": 8,
    "Capricorn": 9,
    "Aquarius": 10,
    "Pisces": 11,
}
