"""ASGI probe mounted in the proxy test stand."""

import json
from collections import Counter

AUTH_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/refresh"}
counts = Counter()


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        return
    path = scope["path"]
    if path in AUTH_PATHS:
        counts[path] += 1
        result = {"client": scope["client"][0]}
    elif path == "/api/proxy-test/counts":
        result = dict(counts)
    elif path == "/api/proxy-test":
        result = {"scheme": scope["scheme"], "client": scope["client"][0]}
    elif path == "/api/proxy-test/upload":
        body_bytes = 0
        while True:
            message = await receive()
            body_bytes += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        result = {"body_bytes": body_bytes}
    else:
        await send({"type": "http.response.start", "status": 404})
        await send({"type": "http.response.body", "body": b""})
        return
    body = json.dumps(result).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
