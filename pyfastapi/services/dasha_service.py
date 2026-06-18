import logging
import re
from typing import Dict, List, Tuple

from jhora import utils
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.panchanga import drik

from config import configure_ephemeris_path, ephe_path, suppress_third_party_stdout
from models import HoroscopeRequest
from services.dasha_registry import DASHA_SYSTEMS

logger = logging.getLogger("uvicorn.error")

DASHA_HIERARCHY_DEPTH = 3  # maha + antar + pratyantar


def _jd_to_date_str(jd: float) -> str:
    y, m, d, _ = utils.jd_to_gregorian(jd)
    return f"{y:04d}-{m:02d}-{d:02d}"


def _date_tuple_to_date_str(date_tuple: Tuple) -> str:
    y, m, d, _fractional_hour = date_tuple
    return f"{y:04d}-{m:02d}-{d:02d}"


def _planet_name(planet_int: int) -> str:
    raw = utils.PLANET_NAMES[planet_int]
    return re.sub(r"[^\x00-\x7F]+", "", raw).strip()


def _rasi_name(rasi_int: int) -> str:
    raw = utils.RAASI_LIST[rasi_int]
    return re.sub(r"[^\x00-\x7F]+", "", raw).strip()


def _lord_name(lord_id: int, lord_kind: str) -> str:
    return _planet_name(lord_id) if lord_kind == "planet" else _rasi_name(lord_id)


def _resolve_jd_and_place(data: HoroscopeRequest):
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    tob = (hour, minute, 0)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    configure_ephemeris_path(ephe_path)
    jd = utils.julian_day_number(date_in, tob)
    return date_in, tob, jd, place


def _rows_to_tree(rows: List, lord_kind: str) -> List[Dict]:
    """Group flat [lords_tuple, start_tuple, duration_years] rows (as returned by
    pyjhora's dhasa_level_index=3 contract) into a maha/antar/pratyantar tree.

    The first row for a given maha/antar lord carries that level's start date,
    since pyjhora emits rows depth-first in chronological order.
    """
    dashas: List[Dict] = []
    current_maha = None
    current_antar = None

    for lords_tuple, start_tuple, _duration_years in rows:
        maha_lord, antar_lord, pratyantar_lord = lords_tuple
        start_date = _date_tuple_to_date_str(start_tuple)

        if current_maha is None or current_maha["_lord_id"] != maha_lord:
            current_maha = {
                "_lord_id": maha_lord,
                "lord": _lord_name(maha_lord, lord_kind),
                "start_date": start_date,
                "antardashas": [],
            }
            dashas.append(current_maha)
            current_antar = None

        if current_antar is None or current_antar["_lord_id"] != antar_lord:
            current_antar = {
                "_lord_id": antar_lord,
                "lord": _lord_name(antar_lord, lord_kind),
                "start_date": start_date,
                "pratyantardashas": [],
            }
            current_maha["antardashas"].append(current_antar)

        current_antar["pratyantardashas"].append(
            {"lord": _lord_name(pratyantar_lord, lord_kind), "start_date": start_date}
        )

    for maha in dashas:
        del maha["_lord_id"]
        for antar in maha["antardashas"]:
            del antar["_lord_id"]

    return dashas


def _build_pratyantardashas(
    maha_lord: int, bhukti_lord: int, bhukti_start_jd: float
) -> List[Dict]:
    antara_dict = vimsottari._vimsottari_antara(maha_lord, bhukti_lord, bhukti_start_jd)
    return [
        {
            "lord": _planet_name(antara_lord),
            "start_date": _jd_to_date_str(antara_start_jd),
        }
        for antara_lord, antara_start_jd in antara_dict.items()
    ]


def _build_antardashas(maha_lord: int, maha_start_jd: float) -> List[Dict]:
    bhukti_dict = vimsottari._vimsottari_bhukti(maha_lord, maha_start_jd)
    return [
        {
            "lord": _planet_name(bhukti_lord),
            "start_date": _jd_to_date_str(bhukti_start_jd),
            "pratyantardashas": _build_pratyantardashas(
                maha_lord, bhukti_lord, bhukti_start_jd
            ),
        }
        for bhukti_lord, bhukti_start_jd in bhukti_dict.items()
    ]


def build_dasha_payload(data: HoroscopeRequest) -> Dict:
    """Compute Vimshottari Mahadasha data for the given birth details.

    Returns the dasha balance at birth and all 9 mahadashas, each with
    9 antardashas and 9 pratyantardashas.
    """
    _date_in, _tob, jd, place = _resolve_jd_and_place(data)

    with suppress_third_party_stdout():
        utils.set_language("en")

        vim_bal, _ = vimsottari.get_vimsottari_dhasa_bhukthi(
            jd, place, dhasa_level_index=3
        )
        mahadashas = vimsottari.vimsottari_mahadasa(jd, place)

        balance_years, balance_months, balance_days = vim_bal
        dashas = [
            {
                "lord": _planet_name(maha_lord),
                "start_date": _jd_to_date_str(maha_start_jd),
                "antardashas": _build_antardashas(maha_lord, maha_start_jd),
            }
            for maha_lord, maha_start_jd in mahadashas.items()
        ]

    return {
        "status": "success",
        "data": {
            "balance": {
                "years": balance_years,
                "months": balance_months,
                "days": balance_days,
            },
            "dashas": dashas,
            "system": "vimshottari",
        },
    }


def build_generic_dasha_payload(data: HoroscopeRequest, system: str) -> Dict:
    """Compute a 3-level dasha hierarchy for any registered non-Vimshottari system.

    Relies on the shared pyjhora contract: calling the system's dasha function with
    dhasa_level_index=3 returns a flat list of [lords_tuple, start_tuple, duration_years]
    rows, which _rows_to_tree groups into the same maha/antar/pratyantar shape used by
    Vimshottari. PyJHora does not expose a "balance at birth" figure for these systems.
    """
    spec = DASHA_SYSTEMS[system]
    date_in, tob, jd, place = _resolve_jd_and_place(data)

    with suppress_third_party_stdout():
        utils.set_language("en")

        if spec.input_kind == "jd":
            rows = spec.function(
                jd, place, dhasa_level_index=DASHA_HIERARCHY_DEPTH, **spec.extra_kwargs
            )
        else:
            rows = spec.function(
                date_in, tob, place, dhasa_level_index=DASHA_HIERARCHY_DEPTH, **spec.extra_kwargs
            )

        dashas = _rows_to_tree(rows, spec.lord_kind)

    return {
        "status": "success",
        "data": {
            "balance": None,
            "dashas": dashas,
            "system": system,
        },
    }
