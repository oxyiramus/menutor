import json
import ssl
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

TLS = ssl.create_default_context(cafile="/certs/cert.pem")
PATH = "/api/proxy-test"


def request(origin, headers=None):
    probe = Request(origin + PATH, headers=headers or {})
    with urlopen(probe, context=TLS, timeout=2) as response:
        return json.load(response)


def wait_for_chain():
    deadline = time.monotonic() + 30
    while True:
        try:
            request("https://edge")
            return
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def main():
    wait_for_chain()
    cases = (
        ("HTTPS через TLS-прокси", "https://edge", "http", "https"),
        ("HTTP через TLS-прокси", "http://edge", "https", "http"),
        ("Прямой HTTP во внутренний Nginx", "http://frontend", "https", "http"),
        ("Прямой HTTP в Uvicorn", "http://backend:8000", "https", "http"),
    )
    for label, origin, claimed_scheme, expected_scheme in cases:
        headers = {
            "X-Forwarded-Proto": claimed_scheme,
            "X-Forwarded-For": "192.0.2.10",
            "X-Real-IP": "192.0.2.11",
            "Forwarded": f'for=192.0.2.12;proto={claimed_scheme}',
        }
        actual = request(origin, headers)
        expected = {"scheme": expected_scheme, "client": "172.29.103.4"}
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")
        print(f"{label}: {actual['scheme']} {actual['client']}", flush=True)


if __name__ == "__main__":
    main()
