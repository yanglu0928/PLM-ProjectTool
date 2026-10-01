from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smoke_packaged_platform_write_https import KEY_REFS, smoke  # noqa: E402
from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE  # noqa: E402


class PackagedPlatformWriteSmokeTests(unittest.TestCase):
    def test_synthetic_public_key_uses_actual_embedded_packages_root(self) -> None:
        self.assertEqual(PUBLIC_KEY_RELATIVE,
                         "runtime/python/packages/plm_assistant/modules/license/trust/product_public_key.json")
        self.assertEqual(len(KEY_REFS), 12)
        self.assertEqual(len(set(KEY_REFS)), 12)

    def test_existing_fixed_vault_target_rejects_before_copy(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with patch("smoke_packaged_platform_write_https.verify_layout",
                   return_value={"file_count": 21115, "mapping_sha256": "fixed"}):
            with patch("smoke_packaged_platform_write_https.credential_exists", return_value=True):
                with patch("smoke_packaged_platform_write_https.rehearse") as placement:
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        smoke(*paths)
                    placement.assert_not_called()


if __name__ == "__main__":
    unittest.main()
