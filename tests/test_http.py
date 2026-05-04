import httpx
import pytest

from weather_truth.feeds.http import HttpClient


def test_retries_on_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    client = HttpClient(transport=httpx.MockTransport(handler))
    try:
        result = client.get_json("https://example.test/")
    finally:
        client.close()

    assert result == {"ok": True}
    assert calls["n"] == 3


def test_4xx_does_not_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    client = HttpClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_json("https://example.test/")
    finally:
        client.close()

    assert calls["n"] == 1


def test_5xx_exhausts_retries_and_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="busy")

    client = HttpClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(Exception):
            client.get_json("https://example.test/")
    finally:
        client.close()

    assert calls["n"] == 4
