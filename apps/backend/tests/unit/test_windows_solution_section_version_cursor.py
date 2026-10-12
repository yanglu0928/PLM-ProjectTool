"""Independent fail-closed Windows SectionVersion cursor key tests."""

from __future__ import annotations

import unittest
import uuid
import ctypes
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_section_version_cursor import (
    SECTION_VERSION_LIST_CURSOR_KEY_REF,
    ProductionSectionVersionCursorStartupError,
    create_windows_section_version_list_cursor_codec,
)
from plm_assistant.entrypoints.windows_solution_outline_version_cursor import (
    OUTLINE_VERSION_LIST_CURSOR_KEY_REF,
)
from plm_assistant.modules.solution.api.section_version_list_cursor import (
    SectionVersionListCursorCodec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsSectionVersionCursorTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        ref = "section-version-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, section = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "section-version-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic section cursor backup passphrase long enough",
                    provider=vault)
                before = SectionVersionListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    section_id=section, page_size=1, before_version_no=2)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic section cursor backup passphrase long enough",
                    provider=vault), ref)
                after = SectionVersionListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(2, after.decode(
                    token, session_token=b"s" * 32, project_id=project,
                    section_id=section, page_size=1))
            finally:
                library.CredDeleteW(target, 1, 0)

    def test_dedicated_key_fail_closed_and_cursor_recovery(self):
        self.assertNotEqual(SECTION_VERSION_LIST_CURSOR_KEY_REF,
                            OUTLINE_VERSION_LIST_CURSOR_KEY_REF)
        resolver = Resolver(b"v" * 32)
        before = create_windows_section_version_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(before, SectionVersionListCursorCodec)
        self.assertEqual(resolver.calls, [SECTION_VERSION_LIST_CURSOR_KEY_REF])
        project, section = uuid.uuid4(), uuid.uuid4()
        token = before.encode(session_token=b"s" * 32, project_id=project,
                              section_id=section, page_size=1, before_version_no=2)
        after = create_windows_section_version_list_cursor_codec(
            resolver=Resolver(b"v" * 32))
        self.assertEqual(2, after.decode(
            token, session_token=b"s" * 32, project_id=project,
            section_id=section, page_size=1))
        for bad in (None, b"short", b"v" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionSectionVersionCursorStartupError):
                create_windows_section_version_list_cursor_codec(
                    resolver=Resolver(bad))


if __name__ == "__main__":
    unittest.main()
