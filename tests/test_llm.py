"""Tests for :class:`ai.notes.llm.OllamaClient`.

Network access is fully mocked: ``httpx.AsyncClient.post`` is replaced so the
tests never touch a real Ollama server.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from ai.notes.llm import OllamaClient


def _response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_body is None:
        json_body = {"response": "hello"}
    resp.json.return_value = json_body
    resp.text = str(json_body)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(url="http://test.local/api/generate", model_name="test-model")


async def test_query_returns_response(monkeypatch, client: OllamaClient) -> None:
    async def fake_post(self, url, json):  # noqa: A002
        return _response(json_body={"response": "the answer"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await client.query("prompt") == "the answer"


async def test_query_json_mode_sets_format(monkeypatch, client: OllamaClient) -> None:
    captured: dict = {}

    async def fake_post(self, url, json):  # noqa: A002
        captured.update(json)
        return _response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await client.query("prompt", is_json=True)
    assert captured["format"] == "json"
    assert captured["model"] == "test-model"
    assert captured["options"]["temperature"] == 0.3


async def test_query_non_json_mode_has_no_format(
    monkeypatch, client: OllamaClient
) -> None:
    captured: dict = {}

    async def fake_post(self, url, json):  # noqa: A002
        captured.update(json)
        return _response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await client.query("prompt", is_json=False)
    assert "format" not in captured


async def test_query_respects_temperature(monkeypatch, client: OllamaClient) -> None:
    captured: dict = {}

    async def fake_post(self, url, json):  # noqa: A002
        captured.update(json)
        return _response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await client.query("prompt", temperature=0.9)
    assert captured["options"]["temperature"] == 0.9


async def test_query_missing_response_key_returns_empty(
    monkeypatch, client: OllamaClient
) -> None:
    async def fake_post(self, url, json):  # noqa: A002
        return _response(json_body={})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await client.query("prompt") == ""


async def test_query_raises_on_http_error(monkeypatch, client: OllamaClient) -> None:
    async def fake_post(self, url, json):  # noqa: A002
        return _response(status_code=500)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(httpx.HTTPStatusError):
        await client.query("prompt")


async def test_query_raises_on_transport_error(
    monkeypatch, client: OllamaClient
) -> None:
    async def fake_post(self, url, json):  # noqa: A002
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(httpx.ConnectError):
        await client.query("prompt")


async def test_custom_context_and_predict() -> None:
    client = OllamaClient(
        url="http://x", model_name="m", num_ctx=1024, num_predict=128
    )
    assert client.num_ctx == 1024
    assert client.num_predict == 128
