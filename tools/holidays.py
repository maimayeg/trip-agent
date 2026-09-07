

import httpx
from langchain_core.tools import tool

from tools.logger import get_logger

logger = get_logger("holidays")


@tool
def get_public_holidays(country_code: str, year: int) -> str:
    """Get public holidays for a country in a given year. Use a 2-letter ISO
    country code (e.g. 'JP' for Japan, 'DE' for Germany)."""
    logger.info(f"get_public_holidays called | country={country_code} year={year}")

    try:
        response = httpx.get(
            f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}",
            timeout=10.0,
        )
    except httpx.RequestError as e:
        logger.error(f"Holidays request failed | country={country_code} year={year} error={e}")
        return f"Could not fetch holiday data for {country_code}: network error, try again."

    if response.status_code != 200:
        logger.error(f"Failed to fetch holiday data | country={country_code} year={year}")
        return f"Could not find holiday data for country code: {country_code}"

    try:
        holidays = response.json()
    except ValueError as e:
        logger.error(f"Invalid holiday data | country={country_code} year={year} error={e}")
        return f"Could not parse holiday data for {country_code}: unexpected response format."

    if not holidays:
        logger.warning(f"No public holidays found | country={country_code} year={year}")
        return f"No public holidays found for {country_code} in {year}."

    lines = []
    for h in holidays:
        # Nager.Date includes both nationwide holidays and subdivision-specific
        # ones (e.g. only observed in Bavaria) in the same list, distinguished
        # by the 'counties' field. Flatten that distinction into the output so
        # the agent doesn't present a regional holiday as if it applies everywhere.
        counties = h.get("counties")
        scope = "nationwide" if not counties else f"regional ({', '.join(counties)})"
        lines.append(f"{h['date']}: {h['name']} — {scope}")

    logger.info(f"Public holidays found | country={country_code} year={year} count={len(holidays)}")
    return "\n".join(lines)