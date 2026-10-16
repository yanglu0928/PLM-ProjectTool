from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preflight_windows_caddy_go_formal_install import (  # noqa: E402
    preflight, tls_certificate_codes, valid_public_host,
)
from smoke_caddy_same_origin_https import synthetic_certificate  # noqa: E402


class FormalInstallPreflightTests(unittest.TestCase):
    def test_bad_layout_fails_before_target_inspection(self) -> None:
        with patch("preflight_windows_caddy_go_formal_install.verify_layout",
                   side_effect=ValueError("layout rejected")):
            with patch("preflight_windows_caddy_go_formal_install.tls_certificate_codes") as tls:
                with self.assertRaisesRegex(ValueError, "layout rejected"):
                    preflight(Path("a"), Path("b"), Path("c"), Path("d"),
                              install_root=r"C:\PLMTool", target_account=None,
                              public_host=None, tls_cert=None, tls_key=None)
                tls.assert_not_called()

    def test_missing_inputs_have_explicit_fail_closed_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("preflight_windows_caddy_go_formal_install.verify_layout",
                       return_value={"file_count": 21115, "mapping_sha256": "fixed"}):
                report = preflight(Path("a"), Path("b"), Path("c"), Path(directory),
                                   install_root=r"C:\PLMTool", target_account=None,
                                   public_host=None, tls_cert=None, tls_key=None)
        self.assertFalse(report["release_eligible"])
        self.assertFalse(report["install_authorized"])
        self.assertIn("TARGET_SERVICE_ACCOUNT_NOT_IDENTIFIED", report["blocker_codes"])
        self.assertIn("PUBLIC_DNS_NAME_MISSING_OR_INVALID", report["blocker_codes"])
        self.assertIn("FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED", report["blocker_codes"])
        self.assertEqual(report["verified_layout_file_count"], 21115)

    def test_host_and_certificate_inputs_reject_local_or_missing(self) -> None:
        self.assertFalse(valid_public_host("localhost"))
        self.assertFalse(valid_public_host("127.0.0.1"))
        self.assertFalse(valid_public_host("bad host.example"))
        self.assertTrue(valid_public_host("plm.example.com"))
        self.assertEqual(tls_certificate_codes("plm.example.com", None, None),
                         ["TLS_CERTIFICATE_AND_KEY_NOT_SUPPLIED"])

    def test_matching_key_but_wrong_dns_san_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cert, key = Path(directory) / "cert.pem", Path(directory) / "key.pem"
            synthetic_certificate(cert, key)
            self.assertEqual(tls_certificate_codes("plm.example.com", cert, key),
                             ["TLS_CERTIFICATE_DNS_SAN_MISMATCH"])


if __name__ == "__main__":
    unittest.main()
