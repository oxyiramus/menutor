"""Check ingress quota settings without a running Docker daemon."""

from pathlib import Path
import unittest


class IngressRateConfigTest(unittest.TestCase):
    config = (Path(__file__).resolve().parents[2] / ".docker/prod/nginx.conf").read_text()

    def test_separate_shared_zones_use_the_trusted_client_address(self):
        for route in ("login", "register"):
            with self.subTest(route=route):
                key = f"auth_{route}_key"
                zone = f"auth_{route}"
                self.assertRegex(
                    self.config,
                    rf'map \$uri \${key} \{{\s+default "";\s+'
                    rf"~\^/api/auth/{route}\$ \$client_address;\s+\}}",
                )
                self.assertRegex(
                    self.config, rf"limit_req_zone \${key} zone={zone}:\d+m rate=5r/m;"
                )
                self.assertIn(f"limit_req zone={zone} burst=10 nodelay;", self.config)

    def test_rejections_return_429(self):
        self.assertIn("limit_req_status 429;", self.config)


if __name__ == "__main__":
    unittest.main()
