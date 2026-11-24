"""Check the Compose trust boundary with Uvicorn middleware without sockets."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uvicorn import Config

ROOT = Path(__file__).resolve().parents[2]


def compose_services():
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        project = Path(directory)
        shutil.copyfile(ROOT / "docker-compose.yml", project / "docker-compose.yml")
        (project / ".config").mkdir()
        (project / ".config/.env").touch()
        (project / ".config/proxy-trust.conf").touch()
        output = subprocess.check_output(
            ["docker", "compose", "config", "--format", "json"],
            cwd=project,
            env={**os.environ, "VERSION": "test"},
        )
    return json.loads(output)["services"]


class ProxyTrustTest(unittest.IsolatedAsyncioTestCase):
    def test_only_frontend_is_published_for_http(self):
        services = compose_services()
        self.assertEqual(services["frontend"]["ports"][0]["host_ip"], "127.0.0.1")
        self.assertEqual(services["frontend"]["ports"][0]["published"], "8080")
        self.assertFalse(services["backend"].get("ports"))

    async def test_forwarded_metadata_depends_on_the_connected_peer(self):
        services = compose_services()
        frontend_networks = services["frontend"]["networks"]
        peer = (frontend_networks.get("default") or {}).get("ipv4_address", "172.29.103.3")
        observed = []

        async def app(scope, receive, send):
            observed.append((scope["scheme"], scope["client"][0]))

        allowed = services["backend"].get("environment", {}).get("FORWARDED_ALLOW_IPS")
        forwarded = {} if allowed is None else {"FORWARDED_ALLOW_IPS": allowed}
        with patch.dict(os.environ, forwarded, clear=True):
            config = Config(app, interface="asgi3", lifespan="off", log_config=None)
            config.load()

        for sender, scheme, expected in (
            (peer, b"https", ("https", "192.0.2.10")),
            (peer, b"http", ("http", "192.0.2.10")),
            ("172.29.103.20", b"https", ("http", "172.29.103.20")),
            ("127.0.0.1", b"https", ("http", "127.0.0.1")),
        ):
            with self.subTest(sender=sender, scheme=scheme):
                scope = {
                    "type": "http",
                    "scheme": "http",
                    "client": (sender, 12345),
                    "headers": [
                        (b"x-forwarded-proto", scheme),
                        (b"x-forwarded-for", b"192.0.2.10"),
                    ],
                }
                await config.loaded_app(scope, None, None)
                self.assertEqual(observed.pop(), expected)


if __name__ == "__main__":
    unittest.main()
