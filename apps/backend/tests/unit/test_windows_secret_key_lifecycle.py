from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretState,
)
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    SecretKeyLifecycleError, export_backup, provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PASS = "synthetic recovery passphrase with enough length"


class FakeProvider:
    def __init__(self) -> None:
        self.keys: dict[str, bytes] = {}

    def resolve_key(self, key_ref: str) -> bytes | None:
        return self.keys.get(key_ref)

    def install_new(self, key_ref: str, master_key: bytes) -> None:
        if key_ref in self.keys:
            raise RuntimeError("exists")
        self.keys[key_ref] = master_key


class SecretKeyLifecycleTests(unittest.TestCase):
    def test_new_export_restore_and_no_overwrite(self) -> None:
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "new.json"
            provision_new(key_ref="test-v1", backup_path=backup,
                          passphrase=_PASS, provider=provider)
            original = provider.keys["test-v1"]
            self.assertEqual(len(original), 32)
            with self.assertRaises(SecretKeyLifecycleError):
                provision_new(key_ref="test-v1", backup_path=Path(directory) / "other.json",
                              passphrase=_PASS, provider=provider)
            with self.assertRaises(SecretKeyLifecycleError):
                restore_backup(backup_path=backup, passphrase=_PASS, provider=provider)
            self.assertEqual(provider.keys["test-v1"], original)
            second = Path(directory) / "export.json"
            export_backup(key_ref="test-v1", backup_path=second,
                          passphrase=_PASS, provider=provider)
            self.assertNotEqual(second.read_bytes(), backup.read_bytes())
            del provider.keys["test-v1"]
            with self.assertRaises(SecretKeyLifecycleError):
                restore_backup(backup_path=second,
                               passphrase="wrong passphrase with enough length", provider=provider)
            self.assertNotIn("test-v1", provider.keys)
            self.assertEqual(restore_backup(backup_path=second, passphrase=_PASS,
                                            provider=provider), "test-v1")
            self.assertEqual(provider.keys["test-v1"], original)

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_windows_vault_loss_and_recovery(self) -> None:
        provider = WindowsSecretKeyProvider()
        ref = "test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        self.assertIsNone(provider.resolve_key(ref))
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=_PASS, provider=provider)
                original = provider.resolve_key(ref)
                self.assertIsNotNone(original)
                crypto = AesGcmSecretCrypto(provider, key_ref=ref)
                secret_ref = SecretRef(uuid.uuid4())
                draft = crypto.encrypt(
                    secret_ref=secret_ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
                    consumer=SecretConsumer.AI_PROVIDER_ADAPTER, version_no=1,
                    plaintext=bytearray(b"synthetic-before-loss"),
                )
                envelope = SecretEnvelope(
                    secret_ref, SecretPurpose.AI_PROVIDER_KEY, SecretState.ACTIVE,
                    SecretConsumer.AI_PROVIDER_ADAPTER, 1,
                    draft.encrypted_payload, draft.encryption_metadata, draft.key_provider_ref,
                )
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(provider.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup, passphrase=_PASS,
                                                provider=provider), ref)
                self.assertEqual(provider.resolve_key(ref), original)
                self.assertEqual(crypto.decrypt(envelope), bytearray(b"synthetic-before-loss"))
            finally:
                # Only this UUID-scoped synthetic credential is removed.
                library.CredDeleteW(target, 1, 0)
        self.assertIsNone(provider.resolve_key(ref))


if __name__ == "__main__":
    unittest.main()
