from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smoke_packaged_platform_write_https import KEY_REFS, smoke  # noqa: E402
from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE  # noqa: E402


class PackagedPlatformWriteSmokeTests(unittest.TestCase):
    def test_licensed_probe_requires_paired_document_factory(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with self.assertRaisesRegex(ValueError, "must be paired"):
            smoke(*paths, licensed_https_probe=lambda **_kwargs: None)

    def test_malformed_synthetic_document_rejected_before_layout_copy(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with patch("smoke_packaged_platform_write_https.credential_exists", return_value=False):
            with patch("smoke_packaged_platform_write_https.windows_local_macs",
                       return_value=frozenset({"00:11:22:33:44:55"})):
                with patch("smoke_packaged_platform_write_https.rehearse") as placement:
                    with self.assertRaisesRegex(ValueError, "signed document rejected"):
                        smoke(*paths, layout_verifier=lambda *_args: {"file_count": 1},
                              synthetic_license_document_factory=lambda *_args: b"",
                              licensed_https_probe=lambda **_kwargs: None)
                    placement.assert_not_called()

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
