from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_secret_list_cursor import (
    SECRET_LIST_CURSOR_KEY_REF, ProductionSecretCursorStartupError,
    create_windows_secret_list_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PASSPHRASE = "synthetic cursor recovery passphrase with enough length"


class FakeResolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key
        self.refs: list[str] = []

    def resolve_key(self, ref: str) -> bytes | None:
        self.refs.append(ref)
        return self.key


class SecretListCursorWindowsTests(unittest.TestCase):
    def test_dedicated_key_and_missing_key_fail_closed(self) -> None:
        resolver = FakeResolver(b"q" * 32)
        codec = create_windows_secret_list_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [SECRET_LIST_CURSOR_KEY_REF])
        token = codec.encode(
            session_token=b"s" * 32, page_size=1,
            created_at=datetime(2026, 9, 25, tzinfo=timezone.utc), secret_id=uuid.uuid4(),
        )
        self.assertIn(".", token)
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(ProductionSecretCursorStartupError):
                create_windows_secret_list_cursor_codec(resolver=FakeResolver(key))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_vault_loss_and_backup_restore_preserves_cursor(self) -> None:
        # Use a UUID-scoped test ref to avoid touching any production credential.
        ref = "cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "cursor-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=_PASSPHRASE, provider=vault)
                from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
                before = SecretListCursorCodec(vault.resolve_key(ref))
                position = uuid.uuid4()
                instant = datetime(2026, 9, 25, tzinfo=timezone.utc)
                token = before.encode(session_token=b"s" * 32, page_size=50,
                                      created_at=instant, secret_id=position)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup,
                                                passphrase=_PASSPHRASE, provider=vault), ref)
                after = SecretListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(token, session_token=b"s" * 32,
                                              page_size=50), (instant, position))
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
