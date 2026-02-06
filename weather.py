"""Open-Meteo weather integration for DRIP."""

from dataclasses import dataclass
from datetime import datetime

import httpx


WEATHER_CODE_MAP: dict[int, str] = {
    0: "Clear sky",
    1: "Partly cloudy",
    2: "Partly cloudy",
    3: "Partly cloudy",
    45: "Foggy",
    48: "Foggy",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    56: "Drizzle",
    57: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Rain",
    66: "Rain",
    67: "Rain",
    71: "Snow",
    73: "Snow",
    75: "Snow",
    77: "Snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Rain showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


def weather_code_to_condition(code: int) -> str:
    """Convert a WMO weather code to a human-readable condition string."""
    return WEATHER_CODE_MAP.get(code, "Unknown")


@dataclass
class WeatherConditions:
    temp_f: float
    feels_like_f: float
    condition: str
    precipitation: bool
    humidity: int
    wind_mph: float
    raw_code: int
    fetched_at: datetime

    @property
    def summary(self) -> str:
        """One-line summary for outfit prompt."""
        return (
            f"{self.temp_f:.0f}\u00b0F (feels like {self.feels_like_f:.0f}\u00b0F), "
            f"{self.condition}, humidity {self.humidity}%, "
            f"wind {self.wind_mph:.0f}mph"
        )


def fetch_weather(lat: float, lon: float) -> WeatherConditions:
    """Fetch current weather from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }

    resp = httpx.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    current = data["current"]
    code = int(current["weather_code"])

    return WeatherConditions(
        temp_f=float(current["temperature_2m"]),
        feels_like_f=float(current["apparent_temperature"]),
        condition=weather_code_to_condition(code),
        precipitation=float(current.get("precipitation", 0)) > 0,
        humidity=int(current["relative_humidity_2m"]),
        wind_mph=float(current["wind_speed_10m"]),
        raw_code=code,
        fetched_at=datetime.utcnow(),
    )


def parse_weather_response(data: dict) -> WeatherConditions:
    """Parse a raw Open-Meteo API response dict into WeatherConditions.

    Useful for testing and for callers that already have the raw data.
    """
    current = data["current"]
    code = int(current["weather_code"])

    return WeatherConditions(
        temp_f=float(current["temperature_2m"]),
        feels_like_f=float(current["apparent_temperature"]),
        condition=weather_code_to_condition(code),
        precipitation=float(current.get("precipitation", 0)) > 0,
        humidity=int(current["relative_humidity_2m"]),
        wind_mph=float(current["wind_speed_10m"]),
        raw_code=code,
        fetched_at=datetime.utcnow(),
    )
