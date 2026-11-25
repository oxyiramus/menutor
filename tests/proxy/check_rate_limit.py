"""Exercise ingress quotas against the local proxy stand."""

import http.client
import json
import subprocess
import sys
import time


LOGIN = "/api/auth/login"
REGISTER = "/api/auth/register"
REFRESH = "/api/auth/refresh"
PROBE = "/api/proxy-test"


def frontend(project, *args):
    command = ["docker", "compose", "-p", project, "-f", "compose.yml"]
    return subprocess.check_output(
        [*command, "exec", "-T", "frontend", *args], text=True
    ).strip()


def request(path, expected, *, client="127.0.0.1", claimed=1):
    conn = http.client.HTTPConnection(
        "127.0.0.1", 18081, timeout=3, source_address=(client, 0)
    )
    address = f"192.0.2.{claimed}"
    try:
        conn.request(
            "POST" if path.startswith("/api/auth/") else "GET",
            path,
            headers={
                "Connection": "close",
                "X-Forwarded-For": address,
                "X-Real-IP": address,
                "Forwarded": f"for={address}",
            },
        )
        response = conn.getresponse()
        body = response.read()
        assert response.status == expected, (
            f"{path} ({client}): expected {expected}, got {response.status}"
        )
        if expected == 200:
            return json.loads(body)
    finally:
        conn.close()


def worker_pids(project):
    return set(frontend(
        project, "sh", "-c",
        'pid=$(cat /var/run/nginx.pid) && cat "/proc/$pid/task/$pid/children"',
    ).split())


def main(project):
    workers = worker_pids(project)
    assert len(workers) == 2, f"Expected two frontend workers, got {workers}"
    login_started = time.monotonic()
    for _ in range(11):
        request(LOGIN, 200)
    # A reload replaces both workers while preserving the master's shared zones.
    frontend(project, "nginx", "-s", "reload")
    while time.monotonic() - login_started < 10:
        current = worker_pids(project)
        if len(current) == 2 and current.isdisjoint(workers):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("Frontend workers did not rotate after reload")
    request(LOGIN, 429, claimed=2)
    assert time.monotonic() - login_started < 12, "Login burst took too long"
    print("login: 11 passed, 429 after worker rotation with spoofed headers")

    assert request(PROBE + "/counts", 200) == {LOGIN: 11}
    assert request(LOGIN, 200, client="127.0.0.2") == {"client": "127.0.0.2"}
    for _ in range(11):
        request(REGISTER, 200)
    request(REGISTER, 429, claimed=3)
    assert time.monotonic() - login_started < 12, "Quota isolation check took too long"
    assert request(PROBE + "/counts", 200) == {LOGIN: 12, REGISTER: 11}
    print("register: independent burst, 429, backend counts login=12 register=11")

    started = time.monotonic()
    for _ in range(12):
        request(REFRESH, 200)
        request(PROBE, 200)
    assert time.monotonic() - started < 12, "Refresh and ordinary API check took too long"
    assert request(PROBE + "/counts", 200) == {LOGIN: 12, REGISTER: 11, REFRESH: 12}

    # Nginx stores an integer rate. With 5r/m one slot is available after ~12.05 s.
    time.sleep(13)
    request(LOGIN, 200)
    request(REGISTER, 200)
    assert request(PROBE + "/counts", 200) == {LOGIN: 13, REGISTER: 12, REFRESH: 12}
    print("separate client, refresh, ordinary API and quota recovery: OK")


if __name__ == "__main__":
    main(sys.argv[1])
