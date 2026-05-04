from __future__ import annotations

import os
from typing import Any

from .http import HttpClient

BASE_URL = "https://api.openweathermap.org/data/2.5"


class OpenWeatherAuthError(Exception):
    pass


class OpenWeatherClient:
    """Pure transport layer for OpenWeatherMap's current-weather endpoint.

    units=metric is pinned in the URL so temp arrives in Celsius. The response
    payload has no unit marker, so we trust the request param and document the
    invariant here rather than in the mapper.
    """

    def __init__(
        self,
        api_key: str | None = None,
        http: HttpClient | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get(
            "OPENWEATHER_API_KEY"
        )
        if not self._api_key:
            raise OpenWeatherAuthError(
                "OPENWEATHER_API_KEY not set (export it or put it in .env)"
            )
        self._http = http or HttpClient()

    def current_by_city_id(self, city_id: str) -> dict[str, Any]:
        url = (
            f"{BASE_URL}/weather"
            f"?id={city_id}&units=metric&appid={self._api_key}"
        )
        return self._http.get_json(url)

    def close(self) -> None:
        self._http.close()
