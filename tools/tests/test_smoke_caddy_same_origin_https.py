from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_caddy_same_origin_https import caddyfile


class CaddySameOriginTests(unittest.TestCase):
    def test_routing_keeps_api_and_spa_disjoint(self) -> None:
        config = caddyfile(Path("C:/plm/frontend"), Path("C:/temp/cert.pem"),
                           Path("C:/temp/key.pem"), 20481, 20482)
        self.assertIn("/api/v1/* /health /health/*", config)
        self.assertIn("@unknown_api path /api /api/*", config)
        self.assertIn("try_files {path} /index.html", config)
        self.assertIn("reverse_proxy 127.0.0.1:20481", config)

    def test_unsafe_path_or_shared_port_rejected(self) -> None:
        with self.assertRaises(ValueError):
            caddyfile(Path("relative"), Path("C:/cert"), Path("C:/key"), 20481, 20482)
        with self.assertRaises(ValueError):
            caddyfile(Path("C:/frontend"), Path("C:/cert"), Path("C:/key"), 20481, 20481)


if __name__ == "__main__":
    unittest.main()
