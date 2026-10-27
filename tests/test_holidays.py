import httpx

from tools.holidays import get_public_holidays

JP_2026_URL = "https://date.nager.at/api/v3/PublicHolidays/2026/JP"


# --- Your original two tests, now mocked ----------------------------------


def test_japan_holidays_2026(respx_mock):
    respx_mock.get(JP_2026_URL).respond(
        json=[{"date": "2026-01-01", "name": "New Year's Day", "counties": None}]
    )

    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})

    assert "2026" in result


def test_invalid_country_code(respx_mock):
    # Nager.Date answers 404 for an unknown country code
    respx_mock.get("https://date.nager.at/api/v3/PublicHolidays/2026/ZZ").respond(404)

    result = get_public_holidays.invoke({"country_code": "ZZ", "year": 2026})

    assert "Could not find" in result or "No public holidays" in result


# --- Extra cases ------------------------------------------------------------


def test_nationwide_and_regional_holidays(respx_mock):
    respx_mock.get(JP_2026_URL).respond(
        json=[
            {"date": "2026-01-01", "name": "New Year's Day", "counties": None},
            {"date": "2026-06-23", "name": "Okinawa Memorial Day", "counties": ["JP-47"]},
        ]
    )

    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})

    assert result.splitlines() == [
        "2026-01-01: New Year's Day — nationwide",
        "2026-06-23: Okinawa Memorial Day — regional (JP-47)",
    ]


def test_empty_list(respx_mock):
    respx_mock.get(JP_2026_URL).respond(json=[])

    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})

    assert result == "No public holidays found for JP in 2026."


def test_invalid_json(respx_mock):
    respx_mock.get(JP_2026_URL).respond(text="<html>oops</html>")

    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})

    assert result == "Could not parse holiday data for JP: unexpected response format."


def test_network_error(respx_mock):
    respx_mock.get(JP_2026_URL).mock(side_effect=httpx.ConnectError("offline"))

    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})

    assert result == "Could not fetch holiday data for JP: network error, try again."
