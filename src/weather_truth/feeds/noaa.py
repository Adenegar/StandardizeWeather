from __future__ import annotations

from typing import Any

from .http import HttpClient

BASE_URL = "https://api.weather.gov"


class NoaaClient:
    """Pure transport layer for the NOAA api.weather.gov REST API."""

    def __init__(self, http: HttpClient | None = None) -> None:
        self._http = http or HttpClient()

    def latest_observation(self, station_id: str) -> dict[str, Any]:
        return self._http.get_json(
            f"{BASE_URL}/stations/{station_id}/observations/latest"
        )

    def close(self) -> None:
        self._http.close()
