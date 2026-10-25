"""Review list dedicated current-account key and recovery tests."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_review_list_cursor import (
    REVIEW_LIST_CURSOR_KEY_REF,
    ProductionReviewListCursorStartupError,
    create_windows_review_list_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new,
    restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.review.api.list_cursor import ReviewListCursorCodec
from plm_assistant.modules.review.application.list_contract import ReviewListPosition


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsReviewListCursorTests(unittest.TestCase):
    def test_dedicated_key_and_fail_closed(self):
        self.assertEqual(REVIEW_LIST_CURSOR_KEY_REF, "review-list-cursor-v1")
        self.assertNotIn(REVIEW_LIST_CURSOR_KEY_REF, (
            "project-structured-spec-version-list-cursor-v1",
            "document-list-cursor-v1",
            "project-member-list-cursor-v1",
        ))
        resolver = Resolver(b"r" * 32)
        codec = create_windows_review_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, ReviewListCursorCodec)
        self.assertEqual(resolver.calls, [REVIEW_LIST_CURSOR_KEY_REF])
        for bad in (None, b"short", b"r" * 31, b"r" * 33):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionReviewListCursorStartupError):
                create_windows_review_list_cursor_codec(
                    resolver=Resolver(bad),
                )

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        key_ref = "review-list-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + key_ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project = uuid.uuid4()
        position = ReviewListPosition(
            datetime(2026, 10, 19, tzinfo=timezone.utc), uuid.uuid4(),
        )
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "review-list-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=key_ref,
                    backup_path=backup,
                    passphrase="synthetic review list cursor backup phrase",
                    provider=vault,
                )
                before = ReviewListCursorCodec(vault.resolve_key(key_ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    view="my_pending", page_size=25, position=position,
                )
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(key_ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic review list cursor backup phrase",
                    provider=vault,
                ), key_ref)
                after = ReviewListCursorCodec(vault.resolve_key(key_ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32, project_id=project,
                    view="my_pending", page_size=25,
                ), position)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
