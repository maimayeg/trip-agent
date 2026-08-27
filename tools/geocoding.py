
from langchain_core.tools import tool
import httpx
from tools.logger import get_logger

logger = get_logger("geocoding")

def geocode_city(city: str, country_code: str) -> dict:
    """Plain function: resolves a city to lat/lon. Raises ValueError if not found."""
    logger.info(f"geocode_city called | city={city} country={country_code}")
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, {country_code}", "format": "json", "limit": 1},
            headers={"User-Agent": "trip-agent/0.1"}
        )
        response.raise_for_status()
  
        geo = response.json()
    except httpx.RequestError as e:
        logger.error(f"Geocoding request failed | city={city} error={e}")
        return f"Could not fetch geocode for {city}: network error, try again"
    if not geo:
        logger.warning(f"Geocoding failed | city={city} country={country_code}")
        raise ValueError(f"Could not find location: {city}")
    return {"lat": geo[0]["lat"], "lon": geo[0]["lon"]}

@tool
def get_geocode(city: str, country_code: str) -> str:
    """Resolve a city name to latitude/longitude. Use a 2-letter ISO country
    code (e.g. 'JP' for Japan) to disambiguate cities with the same name."""
    try:
        loc = geocode_city(city, country_code)
    except ValueError as e:
        return str(e)
    return f"{city}, {country_code}: lat={loc['lat']}, lon={loc['lon']}"