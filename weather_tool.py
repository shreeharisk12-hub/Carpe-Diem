import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_json(url, params):
    full_url = url + "?" + urlencode(params)

    request = Request(
        full_url,
        headers={"User-Agent": "Brahma-Weather-Demo/1.0"}
    )

    with urlopen(request, timeout=8) as response:
        return json.load(response)


def get_weather(location, day="today"):
    try:
        location = str(location).strip()[:100]
        day = str(day).lower().strip()

        if not location:
            return {"error": "Please provide a place name."}

        if day not in ("today", "tomorrow"):
            return {
                "error": "Supported forecast periods: today, tomorrow."
            }

        places = get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {
                "name": location,
                "count": 5,
                "language": "en",
                "format": "json"
            }
        ).get("results", [])

        if not places:
            return {
                "error": "Location not found.",
                "location_requested": location
            }

        # Prefer Indian results for Brahma's initial audience.
        place = next(
            (p for p in places if p.get("country_code") == "IN"),
            places[0]
        )

        forecast = get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "precipitation,weather_code"
                ),
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,"
                    "precipitation_probability_max,"
                    "weather_code"
                ),
                "forecast_days": 3,
                "timezone": "auto"
            }
        )

        daily = forecast["daily"]
        index = 0 if day == "today" else 1

        result = {
            "location": place["name"],
            "region": place.get("admin1", ""),
            "country": place.get("country", ""),
            "forecast_date": daily["time"][index],
            "period": day,
            "temperature_max_c": daily[
                "temperature_2m_max"
            ][index],
            "temperature_min_c": daily[
                "temperature_2m_min"
            ][index],
            "rainfall_mm": daily[
                "precipitation_sum"
            ][index],
            "max_rain_probability_percent": daily[
                "precipitation_probability_max"
            ][index],
            "weather_code": daily[
                "weather_code"
            ][index],
            "source": "Open-Meteo"
        }

        if day == "today":
            result["current"] = forecast.get("current", {})

        return result

    except Exception as error:
        return {
            "error": "Weather service temporarily unavailable.",
            "error_type": type(error).__name__
        }


if __name__ == "__main__":
    import sys

    location = sys.argv[1] if len(sys.argv) > 1 else "Bengaluru"
    day = sys.argv[2] if len(sys.argv) > 2 else "today"

    print(json.dumps(
        get_weather(location, day),
        indent=2,
        ensure_ascii=False
    ))
