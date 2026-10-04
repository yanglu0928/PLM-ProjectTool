from __future__ import annotations

import sys
import tarfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map_caddy_vendor_license_sources import direct_license_paths, module_versions  # noqa: E402


class CaddyVendorSourceTests(unittest.TestCase):
    def test_duplicate_module_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module_versions("# example.com/a v1.0.0\n# example.com/a v1.1.0\n")

    def test_only_direct_regular_license_like_files(self) -> None:
        def info(name: str, type: bytes = tarfile.REGTYPE) -> tarfile.TarInfo:
            item = tarfile.TarInfo(name)
            item.type = type
            return item
        members = {item.name: item for item in (
            info("vendor/example.com/mod/LICENSE"),
            info("vendor/example.com/mod/NOTICE.txt"),
            info("vendor/example.com/mod/sub/LICENSE"),
            info("vendor/example.com/mod/LICENSE-link", tarfile.SYMTYPE),
            info("vendor/example.com/mod2/LICENSE"))}
        self.assertEqual(direct_license_paths(members, "example.com/mod"), [
            "vendor/example.com/mod/LICENSE", "vendor/example.com/mod/NOTICE.txt"])


if __name__ == "__main__":
    unittest.main()
