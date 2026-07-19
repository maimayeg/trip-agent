# tools/weather.py
import httpx
from langchain_core.tools import tool
from tools.logger import get_logger
logger = get_logger("weather")

def get_geocode(city: str, country_code: str) -> dict:
    geo = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, {country_code}", "format": "json", "limit": 1},
        headers={"User-Agent": "trip-agent/0.1"}
    ).json()
    if not geo:
        raise ValueError(f"Could not find location: {city}")
    return {"lat": geo[0]["lat"], "lon": geo[0]["lon"]}

@tool
def get_weather(city: str, country_code: str) -> str:
    """Get a weather forecast for a city. Use the country_code to disambiguate (e.g. 'JP' for Japan)."""
    logger.info(f"get_weather called | city={city} country={country_code}")
    try:
        location = get_geocode(city, country_code)
    except ValueError as e:
        logger.error(f"Geocoding failed | city={city} error={e}")
        return str(e)
    logger.info(f"Geocoding success | lat={location['lat']} lon={location['lon']}")
    lat, lon = location["lat"], location["lon"]

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