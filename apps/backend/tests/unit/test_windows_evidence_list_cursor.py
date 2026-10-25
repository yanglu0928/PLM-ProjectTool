from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_evidence_list_cursor import (
    EVIDENCE_LIST_CURSOR_KEY_REF, ProductionEvidenceCursorStartupError,
    create_windows_evidence_list_cursor_codec,
)
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PASSPHRASE = "synthetic Evidence cursor recovery passphrase with enough length"


class FakeResolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key
        self.refs: list[str] = []

    def resolve_key(self, ref: str) -> bytes | None:
        self.refs.append(ref)
        return self.key


class EvidenceCursorWindowsTests(unittest.TestCase):
    def test_dedicated_reference_and_missing_key_fail_closed(self):
        resolver = FakeResolver(b"e" * 32)
        codec = create_windows_evidence_list_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [EVIDENCE_LIST_CURSOR_KEY_REF])
        project, evidence = uuid.uuid4(), uuid.uuid4()
        position = datetime(2026, 10, 1, tzinfo=timezone.utc)
        token = codec.encode(session_token=b"s" * 32, scope="PROJECT",
                             project_id=project, page_size=50,
                             created_at=position, evidence_id=evidence)
        self.assertEqual(codec.decode(token, session_token=b"s" * 32,
                                      scope="PROJECT", project_id=project,
                                      page_size=50), (position, evidence))
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(ProductionEvidenceCursorStartupError):
                create_windows_evidence_list_cursor_codec(resolver=FakeResolver(key))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_vault_loss_and_backup_restore_preserves_cursor(self):
        ref = "evidence-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "evidence-cursor-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=_PASSPHRASE, provider=vault)
                project, evidence = uuid.uuid4(), uuid.uuid4()
                position = datetime(2026, 10, 1, tzinfo=timezone.utc)
                before = EvidenceListCursorCodec(vault.resolve_key(ref))
                token = before.encode(session_token=b"s" * 32, scope="PROJECT",
                                      project_id=project, page_size=50,
                                      created_at=position, evidence_id=evidence)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup,
                                                passphrase=_PASSPHRASE,
                                                provider=vault), ref)
                after = EvidenceListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(token, session_token=b"s" * 32,
                                              scope="PROJECT", project_id=project,
                                              page_size=50), (position, evidence))
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
