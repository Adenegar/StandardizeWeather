from __future__ import annotations

import re
from typing import Any

import httpx

_SECRET_PARAM_RE = re.compile(r"(appid|api_?key|token)=([^&\s]+)", re.IGNORECASE)


def _redact(url: str) -> str:
    return _SECRET_PARAM_RE.sub(r"\1=REDACTED", url)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "StandardizeWeather/0.1 (github.com/Adenegar/StandardizeWeather)"


class RetryableStatus(Exception):
    """Raised internally for 5xx responses to trigger a tenacity retry."""


class HttpClient:
    """Thin wrapper over httpx.Client with a sane User-Agent and 5xx retry."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/geo+json,application/json",
            },
            transport=transport,
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, RetryableStatus)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.2, max=2),
        reraise=True,
    )
    def get_json(self, url: str) -> dict[str, Any]:
        resp = self._client.get(url)
        if 500 <= resp.status_code < 600:
            raise RetryableStatus(f"{resp.status_code} from {_redact(url)}")
        if not resp.is_success:
            raise httpx.HTTPStatusError(
                f"{resp.status_code} from {_redact(url)}",
                request=resp.request,
                response=resp,
            )
        return resp.json()

    def close(self) -> None:
        self._client.close()
