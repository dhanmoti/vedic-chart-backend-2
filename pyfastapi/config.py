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

# pyjhora 4.8.6 made drik.vaara() require `place`, but its own internal callers
# (jhora/horoscope/main.py:135, jhora/panchanga/surya_sidhantha.py:43) were not
# updated and still call vaara(jd) with no place, raising TypeError.
from jhora.panchanga import drik

_original_vaara = drik.vaara


def _vaara_compat(jd, place=None, show_vedic_day=True):
    if place is None:
        return drik.civil_weekday(jd)
    return _original_vaara(jd, place, show_vedic_day)


drik.vaara = _vaara_compat

# pyjhora 4.8.6's own sub_planet_list_1 dict (jhora/horoscope/main.py) references
# resource keys that don't exist in its bundled lang files (e.g. 'yama_str' /
# 'yama_short_str' instead of the actual 'yama_ghantaka_str' / 'yama_ghantaka_short_str').
# Backfill known aliases after every resource-file load so missing keys resolve
# to their real equivalent instead of raising KeyError deep inside pyjhora.
from jhora import utils as jhora_utils

_RESOURCE_KEY_ALIASES = {
    "yama_str": "yama_ghantaka_str",
    "yama_short_str": "yama_ghantaka_short_str",
}

_original_read_resource_messages = jhora_utils._read_resource_messages_from_file


def _read_resource_messages_compat(message_file):
    messages = _original_read_resource_messages(message_file)
    for missing_key, fallback_key in _RESOURCE_KEY_ALIASES.items():
        if missing_key not in messages and fallback_key in messages:
            messages[missing_key] = messages[fallback_key]
    return messages


jhora_utils._read_resource_messages_from_file = _read_resource_messages_compat

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
