# tools/weather.py
import httpx
from langchain_core.tools import tool

@tool
def get_weather(city: str, country_code: str) -> str:
    """Get a weather forecast for a city. Use the country_code to disambiguate (e.g. 'JP' for Japan)."""

    # 1. Geocode city → lat/lon
    geo = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, {country_code}", "format": "json", "limit": 1},
        headers={"User-Agent": "trip-agent/0.1"}  # required by Nominatim ToS
    ).json()

    if not geo:
        return f"Could not find location: {city}"

    lat, lon = geo[0]["lat"], geo[0]["lon"]

    # 2. Fetch forecast
    weather = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,weathercode",
            "forecast_days": 7,
            "timezone": "auto"
        }
    ).json()

    daily = weather["daily"]
    lines = []
    for i, date in enumerate(daily["time"]):
        lines.append(
            f"{date}: {daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
            f"rain: {daily['precipitation_sum'][i]}mm"
        )

    return "\n".join(lines)