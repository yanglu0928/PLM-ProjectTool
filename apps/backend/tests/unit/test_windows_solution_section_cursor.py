"""SolutionSection cursor current-account key and recovery tests."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline_cursor import OUTLINE_LIST_CURSOR_KEY_REF
from plm_assistant.entrypoints.windows_solution_reference_cursor import (
    GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF, REFERENCE_LIST_CURSOR_KEY_REF,
)
from plm_assistant.entrypoints.windows_solution_section_cursor import (
    SECTION_LIST_CURSOR_KEY_REF, ProductionSectionCursorStartupError,
    create_windows_section_list_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsSectionCursorTests(unittest.TestCase):
    def test_dedicated_key_and_fail_closed(self):
        self.assertNotIn(SECTION_LIST_CURSOR_KEY_REF, (
            OUTLINE_LIST_CURSOR_KEY_REF,
            REFERENCE_LIST_CURSOR_KEY_REF, GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF,
            "document-list-cursor-v1"))
        resolver = Resolver(b"s" * 32)
        codec = create_windows_section_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, SectionListCursorCodec)
        self.assertEqual(resolver.calls, [SECTION_LIST_CURSOR_KEY_REF])
        for bad in (None, b"short", b"s" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionSectionCursorStartupError):
                create_windows_section_list_cursor_codec(resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        ref = "section-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, section = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "section-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic section cursor backup passphrase long enough",
                    provider=vault)
                before = SectionListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    page_size=25, section_id=section)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic section cursor backup passphrase long enough",
                    provider=vault), ref)
                after = SectionListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, page_size=25), section)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
