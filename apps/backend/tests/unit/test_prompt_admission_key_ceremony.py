from __future__ import annotations

import base64
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[4] / "tools/developer-workbench/prompt_admission_key_ceremony.py"
_SPEC = importlib.util.spec_from_file_location("prompt_key_ceremony_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
ceremony = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ceremony)
_PASS = b"synthetic-only-prompt-ceremony-passphrase"


class PromptAdmissionKeyCeremonyTests(unittest.TestCase):
    def test_create_verify_offline_copy_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            public = Path(directory) / "public.json"
            password = bytearray(_PASS)
            ceremony.create_pair(private, public, password)
            self.assertEqual(password, bytearray(len(password)))
            self.assertTrue(private.read_bytes().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
            value = json.loads(public.read_bytes())
            self.assertEqual(value["key_ref"], "plm-prompt-admission-release-v1")
            self.assertEqual(len(base64.b64decode(value["public_key"])), 32)
            ceremony.verify_pair(private, public, bytearray(_PASS))
            copy = Path(directory) / "offline-copy.pem"
            shutil.copyfile(private, copy)
            ceremony.verify_pair(copy, public, bytearray(_PASS))
            previous = (private.read_bytes(), public.read_bytes())
            with self.assertRaises(ceremony.PromptKeyCeremonyError):
                ceremony.create_pair(private, public, bytearray(_PASS))
            self.assertEqual((private.read_bytes(), public.read_bytes()), previous)

    def test_wrong_password_tamper_and_short_password_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            public = Path(directory) / "public.json"
            with self.assertRaises(ceremony.PromptKeyCeremonyError):
                ceremony.create_pair(private, public, bytearray(b"short"))
            self.assertFalse(private.exists())
            ceremony.create_pair(private, public, bytearray(_PASS))
            password = bytearray(b"wrong-synthetic-password-32-bytes")
            with self.assertRaises(ceremony.PromptKeyCeremonyError):
                ceremony.verify_pair(private, public, password)
            self.assertEqual(password, bytearray(len(password)))
            value = json.loads(public.read_bytes())
            value["key_ref"] = "wrong-ref"
            public.write_text(json.dumps(value), encoding="ascii")
            with self.assertRaises(ceremony.PromptKeyCeremonyError):
                ceremony.verify_pair(private, public, bytearray(_PASS))

    def test_cross_license_identity_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            public = Path(directory) / "public.json"
            ceremony.create_pair(private, public, bytearray(_PASS))
            value = json.loads(public.read_bytes())
            value["schema_version"] = "plm.product-public-key.v1"
            value["key_ref"] = "plm-project-tool-release-v1"
            public.write_text(json.dumps(value), encoding="ascii")
            with self.assertRaises(ceremony.PromptKeyCeremonyError):
                ceremony.verify_pair(private, public, bytearray(_PASS))


if __name__ == "__main__":
    unittest.main()
