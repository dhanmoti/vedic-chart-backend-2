from unittest.mock import patch

import pytest
from pydantic import ValidationError

from models import GocharRequest, HoroscopeRequest, PanchangaRequest, VarshaRequest
from routers import horoscope, transit

BASE = {"dob": "1990-07-15", "time": "14:30", "lat": 40.7, "lng": -74.0}


@pytest.mark.parametrize(
    "tz_id,dob,time,expected",
    [
        ("America/New_York", "1990-07-15", "14:30", -4.0),
        ("America/New_York", "1990-01-15", "14:30", -5.0),
        ("Europe/Moscow", "1995-07-01", "12:00", 4.0),
        ("Asia/Kolkata", "1943-06-10", "10:00", 6.5),
        ("Asia/Kolkata", "2000-01-01", "06:00", 5.5),
    ],
)
def test_tz_id_resolves_historical_offset(tz_id, dob, time, expected):
    req = HoroscopeRequest(**{**BASE, "dob": dob, "time": time}, tz_id=tz_id)
    assert req.tz == expected


def test_tz_id_overrides_tz():
    assert HoroscopeRequest(**BASE, tz=5.5, tz_id="Asia/Tokyo").tz == 9.0


def test_tz_only_still_works():
    assert HoroscopeRequest(**BASE, tz=5.5).tz == 5.5


def test_requires_tz_or_tz_id():
    with pytest.raises(ValidationError):
        HoroscopeRequest(**BASE)


def test_unknown_tz_id_rejected():
    with pytest.raises(ValidationError):
        HoroscopeRequest(**BASE, tz_id="Foo/Bar")


def test_gochar_transit_uses_offset_at_transit_date():
    req = GocharRequest(**{**BASE, "dob": "1990-01-15"}, tz_id="America/New_York", transit_date="2026-07-01")
    assert (req.tz, req.transit_tz) == (-5.0, -4.0)


def test_varsha_and_panchanga_accept_tz_id():
    assert VarshaRequest(**BASE, tz_id="America/New_York", year=5).tz == -4.0
    assert PanchangaRequest(date="1990-07-15", lat=1, lng=1, tz_id="America/New_York").tz == -4.0


@pytest.fixture
def auto_correct(monkeypatch):
    monkeypatch.setenv("TZ_AUTO_CORRECT", "true")


def test_naive_current_offset_is_auto_corrected_from_coordinates(auto_correct):
    # Mumbai 1943: client sends today's IST (5.5); wartime offset was 6.5
    req = HoroscopeRequest(dob="1943-06-10", time="10:00", lat=19.076, lng=72.8777, tz=5.5)
    assert (req.tz, req.tz_id) == (6.5, "Asia/Kolkata")
    # New York summer: client sends standard -5
    req = HoroscopeRequest(**BASE, tz=-5.0)
    assert (req.tz, req.tz_id) == (-4.0, "America/New_York")


def test_correct_or_unrelated_tz_is_left_alone(auto_correct):
    assert HoroscopeRequest(**BASE, tz=-4.0).tz_id is None
    req = HoroscopeRequest(**BASE, tz=8.0)
    assert (req.tz, req.tz_id) == (8.0, None)
    req = HoroscopeRequest(dob="2000-01-01", time="06:00", lat=28.6, lng=77.2, tz=5.5)
    assert (req.tz, req.tz_id) == (5.5, None)


@pytest.mark.parametrize("tz", [-4.0, -5.0])
def test_either_offset_of_repeated_dst_hour_is_trusted(auto_correct, tz):
    req = HoroscopeRequest(**{**BASE, "dob": "1990-10-28", "time": "01:30"}, tz=tz)
    assert (req.tz, req.tz_id) == (tz, None)


@pytest.mark.parametrize(
    "router,path,extra",
    [
        (horoscope, "/horoscope", {}),
        (transit, "/transit/gochar", {"transit_date": "2026-07-01"}),
    ],
)
def test_tz_id_request_does_not_share_cache_key_with_plain_tz(app_client, router, path, extra):
    cache = router.CACHE_SERVICE if router is horoscope else router.GOCHAR_CACHE
    # January birth, July transit: same birth offset, different transit offset
    payload = {**BASE, "dob": "1990-01-15", **extra}
    with patch.object(cache, "get", side_effect=RuntimeError("stop")) as get:
        app_client.post(path, json={**payload, "tz": -5.0})
        app_client.post(path, json={**payload, "tz_id": "America/New_York"})
    first, second = [c.args[0] for c in get.call_args_list]
    assert first != second


def test_auto_correct_can_be_disabled(monkeypatch):
    monkeypatch.setenv("TZ_AUTO_CORRECT", "false")
    assert HoroscopeRequest(**BASE, tz=-5.0).tz == -5.0
