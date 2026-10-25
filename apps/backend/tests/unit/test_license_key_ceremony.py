from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from plm_assistant.modules.license.infrastructure.packaged_product_key import PackagedProductKey


_SCRIPT = Path(__file__).resolve().parents[4] / "tools/developer-workbench/license_key_ceremony.py"
_SPEC = importlib.util.spec_from_file_location("license_key_ceremony_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
ceremony = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ceremony)
_PASS = b"synthetic-only-signing-passphrase-32-bytes"


class LicenseKeyCeremonyTests(unittest.TestCase):
    def test_create_verify_no_overwrite_and_wrong_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            public = Path(directory) / "product_public_key.json"
            password = bytearray(_PASS)
            ceremony.create_pair(private, public, password)
            self.assertEqual(password, bytearray(len(password)))
            self.assertTrue(private.read_bytes().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
            self.assertNotIn(b"PRIVATE KEY", public.read_bytes())
            self.assertIsNotNone(PackagedProductKey(read_manifest=public.read_bytes).resolve_public_key(
                "plm-project-tool-release-v1",
            ))
            ceremony.verify_pair(private, public, bytearray(_PASS))
            offline_copy = Path(directory) / "offline-copy.pem"
            shutil.copyfile(private, offline_copy)
            ceremony.verify_pair(offline_copy, public, bytearray(_PASS))
            original_private = private.read_bytes()
            original_public = public.read_bytes()
            with self.assertRaises(ceremony.KeyCeremonyError):
                ceremony.create_pair(private, public, bytearray(_PASS))
            self.assertEqual(private.read_bytes(), original_private)
            self.assertEqual(public.read_bytes(), original_public)
            with self.assertRaises(ceremony.KeyCeremonyError):
                ceremony.verify_pair(private, public,
                                     bytearray(b"wrong-synthetic-passphrase-32-bytes"))
            self.assertEqual(private.read_bytes(), original_private)
            with self.assertRaises(TypeError):
                serialization.load_pem_private_key(original_private, password=None)

    def test_invalid_passphrase_and_public_manifest_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            public = Path(directory) / "product_public_key.json"
            with self.assertRaises(ceremony.KeyCeremonyError):
                ceremony.create_pair(private, public, bytearray(b"short"))
            self.assertFalse(private.exists())
            ceremony.create_pair(private, public, bytearray(_PASS))
            data = public.read_bytes().replace(b"PLM_PROJECT_TOOL", b"OTHER_PRODUCT___")
            public.write_bytes(data)
            with self.assertRaises(ceremony.KeyCeremonyError):
                ceremony.verify_pair(private, public, bytearray(_PASS))
            public.write_bytes(b'{"product_code":"PLM_PROJECT_TOOL","product_code":"PLM_PROJECT_TOOL"}')
            with self.assertRaises(ceremony.KeyCeremonyError):
                ceremony.verify_pair(private, public, bytearray(_PASS))


if __name__ == "__main__":
    unittest.main()
