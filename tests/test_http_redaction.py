import httpx
import pytest

from weather_truth.feeds.http import HttpClient, _redact


def test_redact_appid():
    url = "https://api.openweathermap.org/data/2.5/weather?id=5586437&units=metric&appid=secret123"
    assert "secret123" not in _redact(url)
    assert "appid=REDACTED" in _redact(url)


def test_redact_apikey_variants():
    assert "k1" not in _redact("https://x/?api_key=k1")
    assert "k2" not in _redact("https://x/?apiKey=k2")
    assert "tokval" not in _redact("https://x/?token=tokval")


def test_4xx_error_redacts_secrets(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    client = HttpClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            client.get_json("https://example.test/?appid=topsecret")
    finally:
        client.close()

    assert "topsecret" not in str(exc.value)
    assert "REDACTED" in str(exc.value)


def test_5xx_retryable_error_redacts_secrets():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    client = HttpClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(Exception) as exc:
            client.get_json("https://example.test/?appid=topsecret")
    finally:
        client.close()

    assert "topsecret" not in str(exc.value)
