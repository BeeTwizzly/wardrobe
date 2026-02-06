"""Tests for weather.py - parsing, code-to-condition mapping, and caching."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from weather import (
    WeatherConditions,
    fetch_weather,
    parse_weather_response,
    weather_code_to_condition,
)


# --- Weather code mapping ---


class TestWeatherCodeMapping:
    def test_clear_sky(self):
        assert weather_code_to_condition(0) == "Clear sky"

    def test_partly_cloudy(self):
        assert weather_code_to_condition(1) == "Partly cloudy"
        assert weather_code_to_condition(2) == "Partly cloudy"
        assert weather_code_to_condition(3) == "Partly cloudy"

    def test_foggy(self):
        assert weather_code_to_condition(45) == "Foggy"
        assert weather_code_to_condition(48) == "Foggy"

    def test_drizzle(self):
        for code in (51, 53, 55, 56, 57):
            assert weather_code_to_condition(code) == "Drizzle"

    def test_rain(self):
        for code in (61, 63, 65, 66, 67):
            assert weather_code_to_condition(code) == "Rain"

    def test_snow(self):
        for code in (71, 73, 75, 77):
            assert weather_code_to_condition(code) == "Snow"

    def test_rain_showers(self):
        for code in (80, 81, 82):
            assert weather_code_to_condition(code) == "Rain showers"

    def test_snow_showers(self):
        for code in (85, 86):
            assert weather_code_to_condition(code) == "Snow showers"

    def test_thunderstorm(self):
        for code in (95, 96, 99):
            assert weather_code_to_condition(code) == "Thunderstorm"

    def test_unknown_code(self):
        assert weather_code_to_condition(999) == "Unknown"


# --- Weather parsing ---


SAMPLE_API_RESPONSE = {
    "current": {
        "temperature_2m": 72.5,
        "apparent_temperature": 75.0,
        "precipitation": 0.0,
        "weather_code": 0,
        "wind_speed_10m": 8.5,
        "relative_humidity_2m": 55,
    }
}


RAINY_API_RESPONSE = {
    "current": {
        "temperature_2m": 58.0,
        "apparent_temperature": 55.0,
        "precipitation": 0.5,
        "weather_code": 63,
        "wind_speed_10m": 12.0,
        "relative_humidity_2m": 85,
    }
}


class TestWeatherParsing:
    def test_parse_clear_weather(self):
        w = parse_weather_response(SAMPLE_API_RESPONSE)
        assert w.temp_f == 72.5
        assert w.feels_like_f == 75.0
        assert w.condition == "Clear sky"
        assert w.precipitation is False
        assert w.humidity == 55
        assert w.wind_mph == 8.5
        assert w.raw_code == 0

    def test_parse_rainy_weather(self):
        w = parse_weather_response(RAINY_API_RESPONSE)
        assert w.temp_f == 58.0
        assert w.condition == "Rain"
        assert w.precipitation is True
        assert w.humidity == 85

    def test_summary_format(self):
        w = parse_weather_response(SAMPLE_API_RESPONSE)
        summary = w.summary
        assert "72\u00b0F" in summary
        assert "75\u00b0F" in summary
        assert "Clear sky" in summary
        assert "55%" in summary
        assert "8mph" in summary

    def test_fetched_at_populated(self):
        w = parse_weather_response(SAMPLE_API_RESPONSE)
        assert isinstance(w.fetched_at, datetime)


# --- Fetch with mock ---


class TestFetchWeather:
    @patch("weather.httpx.get")
    def test_fetch_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        w = fetch_weather(39.89, -86.16)
        assert w.temp_f == 72.5
        assert w.condition == "Clear sky"
        mock_get.assert_called_once()

    @patch("weather.httpx.get")
    def test_fetch_passes_correct_params(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetch_weather(40.71, -74.01)

        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["latitude"] == 40.71
        assert call_kwargs[1]["params"]["longitude"] == -74.01
        assert call_kwargs[1]["params"]["temperature_unit"] == "fahrenheit"

    @patch("weather.httpx.get")
    def test_fetch_raises_on_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        with pytest.raises(Exception, match="Network error"):
            fetch_weather(39.89, -86.16)
