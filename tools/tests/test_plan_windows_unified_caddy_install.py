from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_windows_unified_caddy_install import exact_mapping, plan_install, target_name  # noqa: E402


class CaddyInstallPlanTests(unittest.TestCase):
    def test_new_families_and_old_families(self) -> None:
        self.assertEqual(target_name("payload/web/caddy.exe"), "runtime/caddy/caddy.exe")
        self.assertEqual(target_name("payload/third-party-sources/caddy/source.tar.gz"),
                         "app/third-party-sources/caddy/source.tar.gz")
        self.assertEqual(target_name("payload/config/Caddyfile.template"), "config/Caddyfile.template")
        self.assertEqual(target_name("payload/pgsql/bin/postgres.exe"), "runtime/pgsql/bin/postgres.exe")
        self.assertEqual(target_name("manifest.json"), "app/package-metadata/manifest.json")

    def test_unknown_and_case_insensitive_collisions_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unmapped"):
            target_name("payload/unknown/file")
        with self.assertRaisesRegex(ValueError, "source path collision"):
            exact_mapping(["payload/web/caddy.exe", "payload/web/CADDY.exe"])
        with patch("plan_windows_unified_caddy_install.previous_target_name", return_value="runtime/caddy/caddy.exe"):
            with self.assertRaisesRegex(ValueError, "target path collision"):
                exact_mapping(["payload/web/caddy.exe", "payload/other/file"])

    def test_unsafe_root_rejected_before_archive_read(self) -> None:
        with patch("plan_windows_unified_caddy_install.verify") as verify:
            with self.assertRaisesRegex(ValueError, "ASCII"):
                plan_install(Path("missing.zip"), "D:\\中文\\PLM")
            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
