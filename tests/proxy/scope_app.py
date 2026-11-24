"""ASGI probe mounted in the proxy test stand."""

import json


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        return
    if scope["path"] != "/api/proxy-test":
        await send({"type": "http.response.start", "status": 404})
        await send({"type": "http.response.body", "body": b""})
        return
    body = json.dumps(
        {"scheme": scope["scheme"], "client": scope["client"][0]}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
