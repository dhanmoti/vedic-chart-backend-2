import logging
import re
from typing import Dict

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


def build_dasha_payload(data: HoroscopeRequest) -> Dict:
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

        dashas = []
        for maha_lord, maha_start_jd in mahadashas.items():
            bhukti_dict = vimsottari._vimsottari_bhukti(maha_lord, maha_start_jd)
            antardashas = []
            for bhukti_lord, bhukti_start_jd in bhukti_dict.items():
                antara_dict = vimsottari._vimsottari_antara(
                    maha_lord, bhukti_lord, bhukti_start_jd
                )
                pratyantardashas = [
                    {
                        "lord": _planet_name(al),
                        "start_date": _jd_to_date_str(asjd),
                    }
                    for al, asjd in antara_dict.items()
                ]
                antardashas.append({
                    "lord": _planet_name(bhukti_lord),
                    "start_date": _jd_to_date_str(bhukti_start_jd),
                    "pratyantardashas": pratyantardashas,
                })
            dashas.append({
                "lord": _planet_name(maha_lord),
                "start_date": _jd_to_date_str(maha_start_jd),
                "antardashas": antardashas,
            })

    return {
        "status": "success",
        "data": {
            "balance": {
                "years": vim_bal[0],
                "months": vim_bal[1],
                "days": vim_bal[2],
            },
            "dashas": dashas,
        },
    }
