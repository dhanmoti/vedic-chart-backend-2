import logging
import re
from typing import Dict, List

from jhora import utils
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.panchanga import drik

from config import configure_ephemeris_path, ephe_path, suppress_third_party_stdout
from models import HoroscopeRequest

logger = logging.getLogger("uvicorn.error")


def _jd_to_date_str(jd: float) -> str:
    y, m, d, _ = utils.jd_to_gregorian(jd)
    return f"{y:04d}-{m:02d}-{d:02d}"


def _planet_name(planet_int: int) -> str:
    raw = utils.PLANET_NAMES[planet_int]
    return re.sub(r"[^\x00-\x7F]+", "", raw).strip()


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
    year, month, day = [int(p) for p in data.dob.split("-")]
    hour, minute = [int(p) for p in data.time.split(":")]
    date_in = drik.Date(year, month, day)
    place = drik.Place("Birth Place", data.lat, data.lng, data.tz)

    configure_ephemeris_path(ephe_path)

    with suppress_third_party_stdout():
        utils.set_language("en")
        jd = utils.julian_day_number(date_in, (hour, minute, 0))

        vim_bal, _ = vimsottari.get_vimsottari_dhasa_bhukthi(
            jd, place, include_antardhasa=False
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
        },
    }
