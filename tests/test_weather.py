from datetime import date, timedelta

import httpx
import pytest

from tools import weather

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def daily_payload(n_days: int) -> dict:
    """A fake Open-Meteo response with n_days of forecast, starting today."""
    days = [(date.today() + timedelta(days=i)).isoformat() for i in range(n_days)]
    return {
        "daily": {
            "time": days,
            "temperature_2m_min": [5.0 + i for i in range(n_days)],
            "temperature_2m_max": [12.0 + i for i in range(n_days)],
            "precipitation_sum": [0.5 * i for i in range(n_days)],
            "weathercode": [3] * n_days,
        }
    }


def run(**kwargs: str) -> str:
    return weather.get_weather.invoke({"city": "Berlin", **kwargs})


# --- Your original two tests, now mocked ----------------------------------


def test_tokyo_returns_forecast(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=[{"lat": "35.6812", "lon": "139.7671"}])
    respx_mock.get(FORECAST_URL).respond(json=daily_payload(7))

    result = weather.get_weather.invoke({"city": "Tokyo", "country_code": "JP"})

    assert "°C" in result
    assert "rain" in result


def test_unknown_city_returns_error(respx_mock):
    # Nominatim returns an empty list when nothing matches
    respx_mock.get(NOMINATIM_URL).respond(json=[])

    result = weather.get_weather.invoke({"city": "Fakecityxyz", "country_code": "XX"})

    assert "Could not find" in result


# --- Extra cases (geocoding replaced by a fake function) -------------------


@pytest.fixture
def fake_geocode(monkeypatch):
    monkeypatch.setattr(weather, "geocode_city", lambda city, cc=None: {"lat": 52.52, "lon": 13.41})


def test_default_seven_day_forecast(respx_mock, fake_geocode):
    route = respx_mock.get(FORECAST_URL).respond(json=daily_payload(7))

    lines = run().splitlines()

    assert len(lines) == 7
    assert lines[0] == f"{date.today().isoformat()}: 5.0–12.0°C, rain: 0.0mm"
    assert route.calls.last.request.url.params["forecast_days"] == "7"


def test_trip_dates_filter_and_forecast_days(respx_mock, fake_geocode):
    start = date.today() + timedelta(days=2)
    end = date.today() + timedelta(days=4)
    route = respx_mock.get(FORECAST_URL).respond(json=daily_payload(5))

    lines = run(start_date=start.isoformat(), end_date=end.isoformat()).splitlines()

    assert len(lines) == 3
    assert lines[0].startswith(start.isoformat())
    assert lines[-1].startswith(end.isoformat())
    assert route.calls.last.request.url.params["forecast_days"] == "5"


def test_forecast_days_capped_at_max(respx_mock, fake_geocode):
    far = (date.today() + timedelta(days=40)).isoformat()
    route = respx_mock.get(FORECAST_URL).respond(json=daily_payload(16))

    result = run(start_date=far, end_date=far)

    assert route.calls.last.request.url.params["forecast_days"] == "16"
    assert result.startswith("No forecast available for Berlin")


def test_invalid_date_falls_back_to_default(respx_mock, fake_geocode):
    route = respx_mock.get(FORECAST_URL).respond(json=daily_payload(7))

    result = run(start_date="not-a-date")

    assert len(result.splitlines()) == 7
    assert route.calls.last.request.url.params["forecast_days"] == "7"


def test_api_error_response(respx_mock, fake_geocode):
    respx_mock.get(FORECAST_URL).respond(400, json={"error": True, "reason": "bad latitude"})

    assert run() == "Could not fetch weather for Berlin: bad latitude"


def test_network_error_on_forecast(respx_mock, fake_geocode):
    respx_mock.get(FORECAST_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    assert run() == "Could not fetch weather for Berlin: network error, try again."


def test_geocoding_network_error(monkeypatch):
    def offline(city, cc=None):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(weather, "geocode_city", offline)

    assert run() == "Could not look up 'Berlin' right now: network error, try again."
