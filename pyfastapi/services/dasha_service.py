import logging
import re
from typing import Dict, List, Tuple

from jhora import utils
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.panchanga import drik

from config import suppress_third_party_stdout, with_engine_state
from models import HoroscopeRequest
from services.dasha_registry import DASHA_SYSTEMS

logger = logging.getLogger("uvicorn.error")

DASHA_HIERARCHY_DEPTH = 3  # maha + antar + pratyantar


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


def _resolve_birth(data: HoroscopeRequest):
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    tob = (hour, minute, 0)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)
    return date_in, tob, place


# Ref: PVR, Vedic Astrology: An Integrated Approach §18.2, special note 2: "In the second
# cycle, dasa lengths of various rasis are obtained by subtracting the dasa length in the
# first cycle from 12 years."
NARAYANA_CYCLE_YEARS = 12.0


def _date_tuple_to_jd(date_tuple: Tuple) -> float:
    y, m, d, fractional_hour = date_tuple
    return utils.julian_day_number(drik.Date(y, m, d), (fractional_hour, 0, 0))


def _period_end_jd(module, start_jd: float, place, years: float) -> float:
    """End JD of a period, using the dasa module's own boundary rule when it has one.

    PyJHora 5 resolves each boundary from the Sun's actual transit rather than a fixed
    year length (`_bounded_end_jd`), so reusing it keeps both cycles on the same clock.
    """
    end_fn = getattr(module, "_bounded_end_jd", None)
    if callable(end_fn):
        try:
            return float(end_fn(start_jd, place, years))
        except Exception:  # pragma: no cover - fall back to the mean year below
            logger.warning("second cycle: %s._bounded_end_jd failed", module.__name__)
    return start_jd + years * drik.dhasa_year_duration()


def _append_second_cycle(rows: List, place, module) -> List:
    """Append the Narayana-style second cycle to a single-cycle rasi dasa.

    `rows` are PyJHora's flat [lords_tuple, start_tuple, duration_years] rows for one
    cycle. Mahadashas repeat in the same order with length 12 minus their first-cycle
    length; their sub-periods keep the first cycle's order and proportions.
    """
    if not rows:
        return rows

    groups: List[Tuple[int, List]] = []
    for row in rows:
        maha_lord = row[0][0]
        if not groups or groups[-1][0] != maha_lord:
            groups.append((maha_lord, []))
        groups[-1][1].append(row)

    _last_lords, last_start, last_years = rows[-1]
    maha_start_jd = _period_end_jd(module, _date_tuple_to_jd(last_start), place, last_years)

    second_cycle = []
    for _maha_lord, maha_rows in groups:
        raw_years = sum(r[2] for r in maha_rows)
        first_years = raw_years
        # Narayana-family periods are whole years; PyJHora rounds each sub-period, so
        # snap the summed total back before taking the complement.
        if abs(first_years - round(first_years)) < 0.01:
            first_years = float(round(first_years))
        second_years = max(0.0, NARAYANA_CYCLE_YEARS - first_years)
        maha_end_jd = (
            _period_end_jd(module, maha_start_jd, place, second_years) if second_years > 0 else maha_start_jd
        )
        # Sub-periods split the mahadasha's real span in the first cycle's proportions,
        # so they always close exactly on the mahadasha boundary.
        span = maha_end_jd - maha_start_jd
        elapsed_share = 0.0
        for lords, _start, years in maha_rows:
            share = years / raw_years if raw_years > 0 else 1.0 / len(maha_rows)
            child_start_jd = maha_start_jd + elapsed_share * span
            second_cycle.append((lords, utils.jd_to_gregorian(child_start_jd), second_years * share))
            elapsed_share += share
        maha_start_jd = maha_end_jd
    return list(rows) + second_cycle


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


@with_engine_state
def build_dasha_payload(data: HoroscopeRequest) -> Dict:
    """Compute Vimshottari Mahadasha data for the given birth details.

    Returns the dasha balance at birth and all 9 mahadashas, each with
    9 antardashas and 9 pratyantardashas.
    """
    date_in, tob, place = _resolve_birth(data)

    with suppress_third_party_stdout():
        utils.set_language("en")

        vim_bal, rows = vimsottari.get_dhasa_antardhasa(
            date_in, tob, place, dhasa_level_index=DASHA_HIERARCHY_DEPTH
        )
        dashas = _rows_to_tree(rows, "planet")

    balance_years, balance_months, balance_days = vim_bal

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


@with_engine_state
def build_generic_dasha_payload(data: HoroscopeRequest, system: str) -> Dict:
    """Compute a 3-level dasha hierarchy for any registered non-Vimshottari system.

    Relies on the shared pyjhora contract: calling the system's dasha function with
    dhasa_level_index=3 returns a flat list of [lords_tuple, start_tuple, duration_years]
    rows, which _rows_to_tree groups into the same maha/antar/pratyantar shape used by
    Vimshottari. PyJHora does not expose a "balance at birth" figure for these systems.
    """
    spec = DASHA_SYSTEMS[system]
    date_in, tob, place = _resolve_birth(data)

    with suppress_third_party_stdout():
        utils.set_language("en")

        rows = spec.function(
            date_in, tob, place, dhasa_level_index=DASHA_HIERARCHY_DEPTH, **spec.extra_kwargs
        )
        if spec.second_cycle:
            rows = _append_second_cycle(rows, place, spec.module)

        dashas = _rows_to_tree(rows, spec.lord_kind)

    return {
        "status": "success",
        "data": {
            "balance": None,
            "dashas": dashas,
            "system": system,
        },
    }
