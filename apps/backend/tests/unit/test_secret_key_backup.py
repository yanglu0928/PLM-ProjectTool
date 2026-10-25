from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plm_assistant.modules.platform.infrastructure.secret_key_backup import (
    SecretKeyBackupError, decrypt_backup, encrypt_backup, read_backup,
    write_backup,
)


_PASS = "synthetic recovery passphrase with enough length"


class SecretKeyBackupTests(unittest.TestCase):
    def test_authenticated_round_trip_and_tamper(self) -> None:
        key = bytes(range(32))
        payload = encrypt_backup(key_ref="test-v1", master_key=key, passphrase=_PASS)
        self.assertNotIn(key, payload)
        self.assertEqual(decrypt_backup(payload, passphrase=_PASS), ("test-v1", key))
        for wrong in ("wrong passphrase with enough length", ""):
            with self.assertRaises(SecretKeyBackupError):
                decrypt_backup(payload, passphrase=wrong)
        altered = json.loads(payload)
        altered["key_ref"] = "other-v1"
        with self.assertRaises(SecretKeyBackupError):
            decrypt_backup(json.dumps(altered).encode(), passphrase=_PASS)
        altered = json.loads(payload)
        altered["ciphertext"] = altered["ciphertext"][:-2] + "AA"
        with self.assertRaises(SecretKeyBackupError):
            decrypt_backup(json.dumps(altered).encode(), passphrase=_PASS)

    def test_invalid_material_and_exclusive_file(self) -> None:
        for ref, key, password in (
            ("bad/ref", bytes(range(32)), _PASS),
            ("good", b"short", _PASS),
            ("good", bytes(range(32)), "short"),
        ):
            with self.assertRaises(SecretKeyBackupError):
                encrypt_backup(key_ref=ref, master_key=key, passphrase=password)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.json"
            payload = encrypt_backup(
                key_ref="test-v1", master_key=bytes(range(32)), passphrase=_PASS,
            )
            write_backup(path, payload)
            self.assertEqual(read_backup(path), payload)
            with self.assertRaises(SecretKeyBackupError):
                write_backup(path, b"replacement")
            self.assertEqual(read_backup(path), payload)
            with self.assertRaises(SecretKeyBackupError):
                read_backup(Path("relative.json"))


if __name__ == "__main__":
    unittest.main()
