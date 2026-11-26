import atexit
import contextlib
import functools
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

from jhora.panchanga import drik

# pyjhora 4.7.0+ changed its default ayanamsa from LAHIRI to TRUE_PUSHYA (to match
# their desktop JHora software). Pin it back to LAHIRI so chart output stays
# consistent with production and isn't silently re-shifted by a future pyjhora
# release changing this default again.
# Note: pyjhora 4.7.0+ also defaulted Rahu/Ketu to TRUE_NODE (was MEAN_NODE).
# We do NOT pin that back: dhasavarga() (divisional charts) hardcodes
# set_rahu_ketu_as_true_nodes=True as its own default and resets the global
# planet_list mid-request regardless of our setting, so forcing MEAN_NODE
# globally is not reliably achievable without patching multiple internal
# pyjhora call sites. Rahu/Ketu longitudes intentionally use TRUE_NODE.
# Ref: PVR Narasimha Rao, "Vedic Astrology: An Integrated Approach" §1.3.13 ("We will use
# Chitrapaksha/Lahiri ayanamsa"); Santhanam's notes to BPHS ch. 4.
AYANAMSA_MODE = "LAHIRI"
drik.set_ayanamsa_mode(AYANAMSA_MODE)

# pyjhora 5 defaults to a true tropical dasha year. Pin the mean sidereal year,
# which keeps Vimshottari and Ashtottari dates within a day of earlier releases
# (5.x's "true sidereal" is computed per period and drifts by several days).
const.dhasa_year_duration_default = const.DHASA_YEAR_DURATION.MEAN_SIDEREAL_YEAR

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
# Languages the API offers. PyJHora ships more, but only these have been verified.
SUPPORTED_LANGUAGES = ("en", "hi", "ta", "te", "ka", "ml")


# -------------------------------------------------------------------
# Per-thread engine state
# -------------------------------------------------------------------
def ensure_engine_state() -> None:
    """Apply the ayanamsa and ephemeris path in the calling thread.

    Swiss Ephemeris keeps the sidereal mode and the ephemeris path in thread-local
    storage. The module-level calls above only reach the import thread, so a request
    served from FastAPI's threadpool would otherwise fall back to Swiss Ephemeris'
    default sidereal mode (Fagan-Bradley, about 0.88 degrees from Lahiri).
    """
    configure_ephemeris_path(ephe_path)
    drik.set_ayanamsa_mode(AYANAMSA_MODE)


def with_engine_state(func):
    """Decorator for service entry points: set per-thread engine state before computing."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ensure_engine_state()
        return func(*args, **kwargs)

    return wrapper
