import json
import ssl
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

TLS = ssl.create_default_context(cafile="/cert.pem")
PATH = "/api/proxy-test"


def request(origin, headers=None):
    probe = Request(origin + PATH, headers=headers or {})
    with urlopen(probe, context=TLS, timeout=2) as response:
        return json.load(response)


def wait_for_chain(origin):
    deadline = time.monotonic() + 30
    while True:
        try:
            request(origin)
            return
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def check_import_transport(origin):
    file = b"[]" + b" " * (1024 * 1024 - 2)
    multipart_header = (
        b'--upload\r\nContent-Disposition: form-data; name="file"; filename="test.json"'
        b"\r\nContent-Type: application/json\r\n\r\n"
    )
    body = multipart_header + file + b"\r\n--upload--\r\n"
    probe = Request(
        origin + PATH + "/upload",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=upload"},
    )
    with urlopen(probe, context=TLS, timeout=5) as response:
        assert json.load(response) == {"body_bytes": len(body)}
    print(f"{origin}: multipart с файлом 1048576 байт прошёл", flush=True)


def main():
    if sys.argv[1:] == ["host"]:
        cases = (
            ("HTTPS через Nginx хоста", "https://127.0.0.1:18443", "https", "127.0.0.1"),
            ("HTTP через Nginx хоста", "http://127.0.0.1:18081", "http", "127.0.0.1"),
            ("Прямой HTTP с хоста", "http://127.0.0.1:18080", "http", "172.29.103.1"),
        )
    else:
        cases = (
            ("Прямой HTTP в Nginx", "http://frontend", "http", "172.29.103.4"),
            ("Прямой HTTP в Uvicorn", "http://backend:8000", "http", "172.29.103.4"),
        )
    wait_for_chain(cases[0][1])
    for label, origin, expected_scheme, client in cases:
        claimed_scheme = "http" if expected_scheme == "https" else "https"
        headers = {
            "X-Forwarded-Proto": claimed_scheme,
            "X-Forwarded-For": "192.0.2.10",
            "X-Real-IP": "192.0.2.11",
            "Forwarded": f'for=192.0.2.12;proto={claimed_scheme}',
            "X-Menutor-Proxy-Key": "invalid-test-key",
        }
        actual = request(origin, headers)
        expected = {"scheme": expected_scheme, "client": client}
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")
        print(f"{label}: {actual['scheme']} {actual['client']}", flush=True)
        check_import_transport(origin)


if __name__ == "__main__":
    main()
