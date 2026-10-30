from __future__ import annotations

import unittest

from tools.assemble_windows_parent_package_cloud_candidate import (
    DATABASE_CREDENTIAL_TARGET,
    make_startup_preflight,
)


class WindowsParentStartupPreflightTests(unittest.TestCase):
    def test_manifest_records_each_unverified_startup_prerequisite(self):
        result = make_startup_preflight(product_key_present=False)
        self.assertIs(result["formal_startup_ready"], False)
        self.assertIs(result["packaged_product_public_key_resource_present"], False)
        self.assertIs(result["formal_license_trust_verified"], False)
        self.assertEqual(DATABASE_CREDENTIAL_TARGET, result["database_credential_target_reference"])
        self.assertIs(result["database_credential_reference_verified"], False)
        self.assertIs(result["service_identity_acl_verified"], False)
        self.assertIs(result["tls_certificate_configured"], False)
        self.assertIs(result["tls_private_key_configured"], False)
        self.assertEqual({
            "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
            "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
            "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
            "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
            "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
        }, set(result["blocker_codes"]))

    def test_public_key_presence_does_not_claim_other_trust(self):
        result = make_startup_preflight(product_key_present=True)
        self.assertIs(result["packaged_product_public_key_resource_present"], True)
        self.assertIs(result["formal_license_trust_verified"], False)
        self.assertIs(result["database_credential_reference_verified"], False)
        self.assertIs(result["service_identity_acl_verified"], False)
        self.assertIs(result["tls_certificate_configured"], False)
        self.assertIs(result["formal_startup_ready"], False)
        self.assertNotIn("FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED", result["blocker_codes"])


if __name__ == "__main__":
    unittest.main()
