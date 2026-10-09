"""Independent OutlineVersion history cursor key and recovery tests."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline_version_cursor import (
    OUTLINE_VERSION_LIST_CURSOR_KEY_REF,
    ProductionOutlineVersionCursorStartupError,
    create_windows_outline_version_list_cursor_codec,
)
from plm_assistant.entrypoints.windows_solution_outline_cursor import OUTLINE_LIST_CURSOR_KEY_REF
from plm_assistant.entrypoints.windows_solution_section_cursor import SECTION_LIST_CURSOR_KEY_REF
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsOutlineVersionCursorTests(unittest.TestCase):
    def test_dedicated_key_and_fail_closed(self):
        self.assertNotIn(OUTLINE_VERSION_LIST_CURSOR_KEY_REF, (
            OUTLINE_LIST_CURSOR_KEY_REF, SECTION_LIST_CURSOR_KEY_REF,
            "project-reference-list-cursor-v1", "global-reference-list-cursor-v1"))
        resolver = Resolver(b"v" * 32)
        self.assertIsInstance(
            create_windows_outline_version_list_cursor_codec(resolver=resolver),
            OutlineVersionListCursorCodec)
        self.assertEqual(resolver.calls, [OUTLINE_VERSION_LIST_CURSOR_KEY_REF])
        for bad in (None, b"short", b"v" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionOutlineVersionCursorStartupError):
                create_windows_outline_version_list_cursor_codec(
                    resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        ref = "outline-version-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, outline = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "outline-version-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic version cursor backup passphrase long enough",
                    provider=vault)
                before = OutlineVersionListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    outline_id=outline, page_size=1, before_version_no=2)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic version cursor backup passphrase long enough",
                    provider=vault), ref)
                after = OutlineVersionListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, outline_id=outline,
                    page_size=1), 2)
            finally:
                library.CredDeleteW(target, 1, 0)
