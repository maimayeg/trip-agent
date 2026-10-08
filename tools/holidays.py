import httpx
from datetime import datetime
from langchain_core.tools import tool
from tools.logger import get_logger
logger = get_logger("holidays")

@tool
def get_public_holidays(country_code: str, year: int) -> str:
    """Get public holidays for a country in a given year. Use a 2-letter ISO country code (e.g. 'JP' for Japan, 'DE' for Germany)."""
    logger.info(f"get_public_holidays called | country={country_code} year={year}")

    response = httpx.get(
        f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    )

    if response.status_code != 200:
        logger.error(f"Failed to fetch holiday data | country={country_code} year={year}")
        return f"Could not find holiday data for country code: {country_code}"

    holidays = response.json()

    if not holidays:
        logger.warning(f"No public holidays found | country={country_code} year={year}")
        return f"No public holidays found for {country_code} in {year}."

    lines = [f"{h['date']}: {h['name']}" for h in holidays]
    logger.info(f"Public holidays found | country={country_code} year={year} count={len(holidays)}")
    return "\n".join(lines)
