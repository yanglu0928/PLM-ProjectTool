"""StructuredSpec list cursor current-account key and recovery tests."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline_cursor import OUTLINE_LIST_CURSOR_KEY_REF
from plm_assistant.entrypoints.windows_solution_section_cursor import SECTION_LIST_CURSOR_KEY_REF
from plm_assistant.entrypoints.windows_solution_structured_spec_cursor import (
    STRUCTURED_SPEC_LIST_CURSOR_KEY_REF,
    ProductionStructuredSpecCursorStartupError,
    create_windows_structured_spec_list_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.structured_spec_list_cursor import (
    StructuredSpecListCursorCodec,
)


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsStructuredSpecCursorTests(unittest.TestCase):
    def test_dedicated_key_and_fail_closed(self):
        self.assertNotIn(STRUCTURED_SPEC_LIST_CURSOR_KEY_REF, (
            OUTLINE_LIST_CURSOR_KEY_REF, SECTION_LIST_CURSOR_KEY_REF,
            "document-list-cursor-v1"))
        resolver = Resolver(b"x" * 32)
        codec = create_windows_structured_spec_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, StructuredSpecListCursorCodec)
        self.assertEqual(resolver.calls, [STRUCTURED_SPEC_LIST_CURSOR_KEY_REF])
        for bad in (None, b"short", b"x" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionStructuredSpecCursorStartupError):
                create_windows_structured_spec_list_cursor_codec(
                    resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        ref = "structured-spec-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, spec = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "structured-spec-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic structured spec cursor backup phrase",
                    provider=vault)
                before = StructuredSpecListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    page_size=25, before_spec_id=spec)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic structured spec cursor backup phrase",
                    provider=vault), ref)
                after = StructuredSpecListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, page_size=25), spec)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
