from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_packaged_http_frontend import parse_assets  # noqa: E402


class PackagedHttpFrontendTests(unittest.TestCase):
    def test_index_requires_one_js_and_css(self) -> None:
        self.assertEqual(parse_assets('<script src="/assets/a.js"></script><link href="/assets/b.css">'),
                         ["/assets/a.js", "/assets/b.css"])

    def test_unexpected_asset_paths_rejected(self) -> None:
        for html in ('<script src="/assets/a.js"></script>',
                     '<script src="/assets/a.js"></script><link href="/assets/a.js">',
                     '<script src="/other/a.js"></script><link href="/assets/a.css">'):
            with self.assertRaisesRegex(ValueError, "entry assets"):
                parse_assets(html)


if __name__ == "__main__":
    unittest.main()
