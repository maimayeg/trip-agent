from tools.weather import get_weather

def test_tokyo_returns_forecast():
    result = get_weather.invoke({"city": "Tokyo", "country_code": "JP"})
    assert "°C" in result
    assert "rain" in result

def test_unknown_city_returns_error():
    result = get_weather.invoke({"city": "Fakecityxyz", "country_code": "XX"})
    assert "Could not find" in result