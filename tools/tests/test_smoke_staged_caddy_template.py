from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_staged_caddy_template import render


class RenderCaddyTemplateTests(unittest.TestCase):
    def test_placeholder_render_preserves_fallback(self) -> None:
        source = (Path(__file__).resolve().parents[2] / "deploy/windows/Caddyfile.template").read_text(encoding="ascii")
        output = render(source, cert=Path("C:/temp/cert.pem"), key=Path("C:/temp/key.pem"),
                        frontend=Path("C:/plm/frontend"), api_port=20281, https_port=20282)
        self.assertIn("https://localhost:20282", output)
        self.assertIn("https://:20282", output)
        self.assertIn("reverse_proxy 127.0.0.1:20281", output)
        self.assertIn('respond "Misdirected Request" 421', output)

    def test_relative_path_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "path rejected"):
            render("__PUBLIC_HOST__", cert=Path("relative"), key=Path("C:/key"),
                   frontend=Path("C:/frontend"), api_port=20281, https_port=20282)


if __name__ == "__main__":
    unittest.main()
