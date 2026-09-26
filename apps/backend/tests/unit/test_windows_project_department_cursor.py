from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_project_department_cursor import (
    PROJECT_DEPARTMENT_CURSOR_KEY_REF, ProductionDepartmentCursorStartupError,
    create_windows_project_department_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec


_PASSPHRASE = "synthetic department cursor recovery passphrase with enough length"


class FakeResolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key
        self.refs: list[str] = []

    def resolve_key(self, ref: str) -> bytes | None:
        self.refs.append(ref)
        return self.key


class ProjectDepartmentCursorWindowsTests(unittest.TestCase):
    def test_dedicated_key_and_missing_key_fail_closed(self):
        resolver = FakeResolver(b"d" * 32)
        codec = create_windows_project_department_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [PROJECT_DEPARTMENT_CURSOR_KEY_REF])
        project_id, department_id = uuid.uuid4(), uuid.uuid4()
        token = codec.encode(session_token=b"s" * 32, project_id=project_id,
                             page_size=50, department_id=department_id)
        self.assertEqual(codec.decode(token, session_token=b"s" * 32,
                                      project_id=project_id, page_size=50), department_id)
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(ProductionDepartmentCursorStartupError):
                create_windows_project_department_cursor_codec(resolver=FakeResolver(key))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_vault_loss_and_backup_restore_preserves_cursor(self):
        ref = "department-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "department-cursor-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=_PASSPHRASE, provider=vault)
                project_id, department_id = uuid.uuid4(), uuid.uuid4()
                before = DepartmentListCursorCodec(vault.resolve_key(ref))
                token = before.encode(session_token=b"s" * 32,
                                      project_id=project_id, page_size=50,
                                      department_id=department_id)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup,
                                                passphrase=_PASSPHRASE,
                                                provider=vault), ref)
                after = DepartmentListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(token, session_token=b"s" * 32,
                                              project_id=project_id,
                                              page_size=50), department_id)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
