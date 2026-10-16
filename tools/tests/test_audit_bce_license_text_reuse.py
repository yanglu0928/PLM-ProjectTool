from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_bce_license_text_reuse import audit, check_metadata  # noqa: E402


class BceLicenseTextReuseTests(unittest.TestCase):
    def test_exact_declared_license_metadata(self) -> None:
        check_metadata(b"Name: bce-python-sdk\nVersion: 0.9.79\nLicense: Apache License 2.0\n")

    def test_changed_license_declaration_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "declaration differs"):
            check_metadata(b"Name: bce-python-sdk\nVersion: 0.9.79\nLicense: MIT\n")

    def test_bad_candidate_rejected_before_local_material_read(self) -> None:
        with patch("audit_bce_license_text_reuse.verify", side_effect=ValueError("bad candidate")):
            with patch("audit_bce_license_text_reuse.digest") as digest:
                with self.assertRaisesRegex(ValueError, "bad candidate"):
                    audit(*([Path("missing")] * 6))
                digest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
