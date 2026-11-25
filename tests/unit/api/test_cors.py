import asyncio
from importlib.util import find_spec
from runpy import run_path

import httpx
import pytest
from fastapi import FastAPI


def load_app() -> FastAPI:
    spec = find_spec("backend.api.main")
    assert spec is not None and spec.origin is not None
    return run_path(spec.origin)["app"]


async def send_request(method: str, path: str, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=load_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers)


@pytest.mark.parametrize("preflight", [False, True], ids=["response", "preflight"])
@pytest.mark.parametrize(
    ("allowed_origins", "origin", "expected_origin"),
    [
        (
            " https://app.example, https://other.example ",
            "https://app.example",
            "https://app.example",
        ),
        (
            "https://app.example, https://other.example",
            "https://other.example",
            "https://other.example",
        ),
        ("https://app.example", "https://untrusted.example", None),
        ("https://app.example", "null", None),
        ("", "https://app.example", None),
        ("", "null", None),
    ],
)
def test_cors_headers(monkeypatch, allowed_origins, origin, expected_origin, preflight):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", allowed_origins)
    headers = {"Origin": origin}

    if preflight:
        headers["Access-Control-Request-Method"] = "POST"
        headers["Access-Control-Request-Headers"] = "content-type, authorization"
        response = asyncio.run(send_request("OPTIONS", "/api/auth/refresh", headers))
    else:
        response = asyncio.run(send_request("GET", "/openapi.json", headers))
    assert response.status_code == (400 if preflight and not expected_origin else 200)
    assert response.headers.get("Access-Control-Allow-Origin") == expected_origin
    assert "Access-Control-Allow-Credentials" not in response.headers


@pytest.mark.parametrize(
    "origins", ["*", "https://app.example, *", "https://*.example", "null"]
)
def test_rejects_unsafe_origin_config(monkeypatch, origins):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        load_app()


@pytest.mark.parametrize(
    ("file_config", "process_config", "expected_origin"),
    [
        ({}, None, None),
        ({"CORS_ALLOWED_ORIGINS": "https://app.example"}, None, "https://app.example"),
        ({"CORS_ALLOWED_ORIGINS": "https://app.example"}, "", None),
    ],
)
def test_cors_configuration_precedence(
    monkeypatch, file_config, process_config, expected_origin
):
    monkeypatch.setattr("dotenv.dotenv_values", lambda path: file_config)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    if process_config is not None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", process_config)

    response = asyncio.run(
        send_request("GET", "/openapi.json", {"Origin": "https://app.example"})
    )
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == expected_origin
