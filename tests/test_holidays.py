from tools.holidays import get_public_holidays

def test_japan_holidays_2026():
    result = get_public_holidays.invoke({"country_code": "JP", "year": 2026})
    assert "2026" in result

def test_invalid_country_code():
    result = get_public_holidays.invoke({"country_code": "ZZ", "year": 2026})
    assert "Could not find" in result or "No public holidays" in result