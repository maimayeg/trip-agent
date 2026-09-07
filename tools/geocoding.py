import httpx
from langchain_core.tools import tool

from tools.logger import get_logger

logger = get_logger("geocoding")


def geocode_city(city: str, country_code: str | None = None) -> dict:
    """Plain function: resolves a city to lat/lon, optionally disambiguated by country.
    Raises ValueError if not found, httpx.RequestError if the network call fails."""
    logger.info(f"geocode_city called | city={city} country={country_code}")

    params = {"q": city, "format": "json", "limit": 1}
    if country_code:
        params["countrycodes"] = country_code.lower()

    response = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers={"User-Agent": "trip-agent/0.1"},
        timeout=10.0,
    )

    if response.status_code != 200:
        logger.error(f"Geocoding request rejected | city={city} status={response.status_code}")
        raise ValueError(f"Could not look up '{city}': geocoding service returned an error.")

    geo = response.json()

    if not geo:
        logger.warning(f"Geocoding failed | city={city} country={country_code}")
        where = f" in {country_code}" if country_code else ""
        raise ValueError(f"Could not find a location named '{city}'{where}.")

    return {"lat": geo[0]["lat"], "lon": geo[0]["lon"]}


@tool
def get_geocode(city: str, country_code: str = "") -> str:
    """Resolve a city name to latitude/longitude. Provide a 2-letter ISO
    country code (e.g. 'JP' for Japan, 'FR' for France) when known, to
    disambiguate cities that share a name across different countries."""
    try:
        loc = geocode_city(city, country_code or None)
    except ValueError as e:
        return str(e)
    except httpx.RequestError as e:
        logger.error(f"Geocoding request failed | city={city} error={e}")
        return f"Could not look up '{city}' right now: network error, try again."

    where = f"{city}, {country_code}" if country_code else city
    return f"{where}: lat={loc['lat']}, lon={loc['lon']}"