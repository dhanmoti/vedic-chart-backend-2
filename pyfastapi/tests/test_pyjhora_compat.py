import pytest

import config  # noqa: F401  ensures pyjhora compatibility shims are applied
from jhora.horoscope.main import Horoscope
from jhora.panchanga import drik


@pytest.mark.parametrize("language", ["en", "hi", "ta"])
def test_horoscope_pipeline_survives_pyjhora_for_each_language(language):
    """Tripwire for pyjhora upgrades: construct Horoscope and pull calendar +
    horoscope info for each supported language. Both `vaara()` and the
    `yama_str` resource lookup crashed deep inside pyjhora on upgrade to
    4.8.6, before our own service/adapter code ever ran. Catching that here
    means a future pyjhora bump fails in CI instead of as a 500 in prod.
    """
    date_in = drik.Date(1990, 5, 15)
    horoscope = Horoscope(
        latitude=28.6,
        longitude=77.2,
        timezone_offset=5.5,
        date_in=date_in,
        birth_time="10:30",
        language=language,
    )
    assert horoscope.get_horoscope_information() is not None
