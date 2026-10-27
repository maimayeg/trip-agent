import httpx
import pytest

from tools.geocoding import geocode_city, get_geocode

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim returns lat/lon as strings
TOKYO = [{"lat": "35.6812", "lon": "139.7671", "display_name": "Tokyo, Japan"}]


# --- geocode_city (plain function) -----------------------------------------


def test_geocode_city_success(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=TOKYO)

    assert geocode_city("Tokyo") == {"lat": "35.6812", "lon": "139.7671"}


def test_geocode_city_sends_expected_request(respx_mock):
    route = respx_mock.get(NOMINATIM_URL).respond(json=TOKYO)

    geocode_city("Tokyo", "JP")

    request = route.calls.last.request
    assert request.url.params["q"] == "Tokyo"
    assert request.url.params["format"] == "json"
    assert request.url.params["limit"] == "1"
    assert request.url.params["countrycodes"] == "jp"  # lowercased
    assert request.headers["User-Agent"] == "trip-agent/0.1"


def test_geocode_city_omits_countrycodes_when_not_given(respx_mock):
    route = respx_mock.get(NOMINATIM_URL).respond(json=TOKYO)

    geocode_city("Tokyo")

    assert "countrycodes" not in route.calls.last.request.url.params


def test_geocode_city_not_found(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=[])

    with pytest.raises(ValueError, match="Could not find a location named 'Atlantis'."):
        geocode_city("Atlantis")


def test_geocode_city_not_found_mentions_country(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=[])

    with pytest.raises(ValueError, match="'Paris' in JP"):
        geocode_city("Paris", "JP")


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_geocode_city_http_error(respx_mock, status):
    respx_mock.get(NOMINATIM_URL).respond(status)

    with pytest.raises(ValueError, match="geocoding service returned an error"):
        geocode_city("Tokyo")


def test_geocode_city_network_error_propagates(respx_mock):
    respx_mock.get(NOMINATIM_URL).mock(side_effect=httpx.ConnectError("offline"))

    with pytest.raises(httpx.RequestError):
        geocode_city("Tokyo")


# --- get_geocode (LangChain tool) ------------------------------------------


def test_get_geocode_success_with_country(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=TOKYO)

    result = get_geocode.invoke({"city": "Tokyo", "country_code": "JP"})

    assert result == "Tokyo, JP: lat=35.6812, lon=139.7671"


def test_get_geocode_success_without_country(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=TOKYO)

    assert get_geocode.invoke({"city": "Tokyo"}) == "Tokyo: lat=35.6812, lon=139.7671"


def test_get_geocode_not_found_returns_message(respx_mock):
    respx_mock.get(NOMINATIM_URL).respond(json=[])

    assert get_geocode.invoke({"city": "Atlantis"}) == (
        "Could not find a location named 'Atlantis'."
    )


def test_get_geocode_network_error_returns_message(respx_mock):
    respx_mock.get(NOMINATIM_URL).mock(side_effect=httpx.ReadTimeout("timed out"))

    assert get_geocode.invoke({"city": "Tokyo"}) == (
        "Could not look up 'Tokyo' right now: network error, try again."
    )
