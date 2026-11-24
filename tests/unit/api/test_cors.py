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

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=load_app())
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            if preflight:
                headers.update(
                    {
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type, authorization",
                    }
                )
                return await client.options("/api/auth/refresh", headers=headers)
            return await client.get("/openapi.json", headers=headers)

    response = asyncio.run(request())
    assert response.status_code == (400 if preflight and not expected_origin else 200)
    assert response.headers.get("Access-Control-Allow-Origin") == expected_origin
    assert "Access-Control-Allow-Credentials" not in response.headers


@pytest.mark.parametrize("origins", ["*", "https://app.example, *", "null"])
def test_rejects_unsafe_origin_config(monkeypatch, origins):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        load_app()
