# tools/weather.py
from datetime import date

import httpx
from langchain_core.tools import tool

from tools.geocoding import geocode_city
from tools.logger import get_logger

logger = get_logger("weather")

# Open-Meteo's free forecast tier only extends this far into the future.
MAX_FORECAST_DAYS = 16


@tool
def get_weather(
    city: str,
    country_code: str = "",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """Get a weather FORECAST for a city, covering today through the next
    several days only — this cannot provide historical/past weather. Do not
    call this for questions about past dates; say you lack that data instead.
    Provide a 2-letter ISO country code (e.g. 'JP' for Japan) when known, to
    disambiguate cities that share a name across different countries.
    Optionally provide start_date and end_date (YYYY-MM-DD) to get the
    forecast filtered to a specific trip's date range instead of the default
    next-7-days — use this whenever the user gave specific trip dates."""
    logger.info(
        f"get_weather called | city={city} country={country_code} "
        f"start_date={start_date} end_date={end_date}"
    )

    try:
        location = geocode_city(city, country_code or None)
    except ValueError as e:
        logger.error(f"Geocoding failed | city={city} error={e}")
        return str(e)
    except httpx.RequestError as e:
        logger.error(f"Geocoding request failed | city={city} error={e}")
        return f"Could not look up '{city}' right now: network error, try again."

    logger.info(f"Geocoding success | lat={location['lat']} lon={location['lon']}")
    lat, lon = location["lat"], location["lon"]

    # Parse the optional trip date range. Invalid dates are logged and
    # ignored (fall back to the default 7-day window) rather than erroring
    # the whole call — a malformed date shouldn't block an otherwise-valid
    # weather request.
    trip_start = trip_end = None
    today = date.today()
    if start_date:
        try:
            trip_start = date.fromisoformat(start_date)
        except ValueError:
            logger.warning(f"Invalid start_date, ignoring | value={start_date}")
    if end_date:
        try:
            trip_end = date.fromisoformat(end_date)
        except ValueError:
            logger.warning(f"Invalid end_date, ignoring | value={end_date}")

    forecast_days = 7
    if trip_start or trip_end:
        effective_end = trip_end or trip_start
        days_ahead = (effective_end - today).days + 1
        forecast_days = max(1, min(days_ahead, MAX_FORECAST_DAYS))

    # Fetch forecast
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,weathercode",
                "forecast_days": forecast_days,
                "timezone": "auto",
            },
            timeout=10.0,
        )
        weather = response.json()
    except httpx.RequestError as e:
        logger.error(f"Weather API request failed | city={city} error={e}")
        return f"Could not fetch weather for {city}: network error, try again."

    if "daily" not in weather:
        logger.error(f"Weather API error | city={city} response={weather}")
        return f"Could not fetch weather for {city}: {weather.get('reason', 'unknown error')}"

    daily = weather["daily"]

    # Filter down to just the trip's date range before this ever becomes
    # part of the agent's context — the LLM never sees the days outside
    # what was actually asked for.
    indices = range(len(daily["time"]))
    if trip_start or trip_end:
        indices = [
            i
            for i in indices
            if (not trip_start or date.fromisoformat(daily["time"][i]) >= trip_start)
            and (not trip_end or date.fromisoformat(daily["time"][i]) <= trip_end)
        ]
        if not indices:
            logger.warning(
                f"No forecast data in requested range | city={city} "
                f"start={start_date} end={end_date}"
            )
            return (
                f"No forecast available for {city} between {start_date or '?'} and "
                f"{end_date or '?'} — that range may be too far out (forecasts only "
                f"go about {MAX_FORECAST_DAYS} days ahead) or already in the past."
            )

    lines = []
    for i in indices:
        date_str = daily["time"][i]
        temp_min, temp_max = daily["temperature_2m_min"][i], daily["temperature_2m_max"][i]
        rain = daily["precipitation_sum"][i]
        lines.append(f"{date_str}: {temp_min}–{temp_max}°C, rain: {rain}mm")

    return "\n".join(lines)