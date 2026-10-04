from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_trusted_time import (
    ProductionTrustedTimeStartupError, create_windows_trusted_time_integrity,
)
from plm_assistant.modules.license.application.trusted_time import TrustedTimeRecord
from plm_assistant.modules.license.infrastructure.trusted_time_integrity import (
    HmacTrustedTimeIntegrity, TRUSTED_TIME_KEY_REF,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PASS = "synthetic recovery passphrase for trusted time"


class FakeResolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key

    def resolve_key(self, ref: str) -> bytes | None:
        return self.key if ref == TRUSTED_TIME_KEY_REF else None


class WindowsTrustedTimeTests(unittest.TestCase):
    def test_composition_requires_separate_protected_key(self) -> None:
        for key in (None, b"short", b"x" * 33):
            with self.subTest(length=0 if key is None else len(key)):
                with self.assertRaises(ProductionTrustedTimeStartupError):
                    create_windows_trusted_time_integrity(resolver=FakeResolver(key))
        integrity = create_windows_trusted_time_integrity(resolver=FakeResolver(b"t" * 32))
        self.assertTrue(integrity.verify(TrustedTimeRecord(uuid.uuid4(), None, 0, None, None)))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_vault_key_loss_and_recovery_preserves_existing_hmac(self) -> None:
        provider = WindowsSecretKeyProvider()
        ref = "test-time-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "time-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup, passphrase=_PASS,
                              provider=provider)
                integrity = HmacTrustedTimeIntegrity(provider, key_ref=ref)
                record = TrustedTimeRecord(
                    uuid.uuid4(), datetime(2026, 9, 25, tzinfo=timezone.utc),
                    1, None, uuid.uuid4(),
                )
                signed = TrustedTimeRecord(
                    record.state_id, record.last_successful_time, record.state_version,
                    integrity.sign(record), record.last_event_ref,
                )
                self.assertTrue(integrity.verify(signed))
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertFalse(integrity.verify(signed))
                self.assertFalse(integrity.verify(TrustedTimeRecord(uuid.uuid4(), None, 0, None, None)))
                self.assertEqual(restore_backup(backup_path=backup, passphrase=_PASS,
                                                provider=provider), ref)
                self.assertTrue(integrity.verify(signed))
            finally:
                library.CredDeleteW(target, 1, 0)
        self.assertIsNone(provider.resolve_key(ref))


if __name__ == "__main__":
    unittest.main()
