from __future__ import annotations

import unittest
import uuid
import ctypes
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_document_list_cursor import (
    DOCUMENT_LIST_CURSOR_KEY_REF, ProductionDocumentCursorStartupError,
    create_windows_document_list_cursor_codec,
)
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new, restore_backup
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


class _Resolver:
    def __init__(self, key):
        self.key = key
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.key


class DocumentListCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = DocumentListCursorCodec(b"d" * 32)
        self.session = b"s" * 32
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()

    def test_project_and_global_roundtrip(self) -> None:
        for scope, project in (("PROJECT", self.project), ("GLOBAL", None)):
            with self.subTest(scope=scope):
                token = self.codec.encode(
                    session_token=self.session, scope=scope, project_id=project,
                    page_size=25, document_id=self.document,
                )
                self.assertEqual(self.codec.decode(
                    token, session_token=self.session, scope=scope,
                    project_id=project, page_size=25,
                ), self.document)

    def test_tamper_and_cross_context_fail_closed(self) -> None:
        token = self.codec.encode(
            session_token=self.session, scope="PROJECT", project_id=self.project,
            page_size=25, document_id=self.document,
        )
        for changed in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                        token + "x", "bad"):
            with self.subTest(changed=changed), self.assertRaises(ApplicationError):
                self.codec.decode(changed, session_token=self.session,
                                  scope="PROJECT", project_id=self.project,
                                  page_size=25)
        for session, scope, project, size in (
            (b"x" * 32, "PROJECT", self.project, 25),
            (self.session, "PROJECT", uuid.uuid4(), 25),
            (self.session, "GLOBAL", None, 25),
            (self.session, "PROJECT", self.project, 50),
        ):
            with self.subTest(scope=scope, project=project, size=size), self.assertRaises(ApplicationError):
                self.codec.decode(token, session_token=session, scope=scope,
                                  project_id=project, page_size=size)

    def test_invalid_key_and_position_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DocumentListCursorCodec(b"short")
        for scope, project, size, document in (
            ("PROJECT", None, 25, self.document),
            ("GLOBAL", self.project, 25, self.document),
            ("PROJECT", self.project, 0, self.document),
            ("PROJECT", self.project, 25, uuid.UUID(int=0)),
        ):
            with self.subTest(scope=scope, project=project), self.assertRaises(ValueError):
                self.codec.encode(session_token=self.session, scope=scope,
                                  project_id=project, page_size=size,
                                  document_id=document)

    def test_windows_key_is_dedicated_and_required(self) -> None:
        resolver = _Resolver(b"k" * 32)
        codec = create_windows_document_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, DocumentListCursorCodec)
        self.assertEqual(resolver.calls, [DOCUMENT_LIST_CURSOR_KEY_REF])
        with self.assertRaises(ProductionDocumentCursorStartupError):
            create_windows_document_list_cursor_codec(resolver=_Resolver(None))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_windows_vault_loss_and_backup_restore_preserves_cursor(self) -> None:
        ref = "document-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "document-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic document cursor backup passphrase with enough length",
                    provider=vault,
                )
                before = DocumentListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=self.session, scope="PROJECT",
                    project_id=self.project, page_size=25,
                    document_id=self.document,
                )
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic document cursor backup passphrase with enough length",
                    provider=vault,
                ), ref)
                after = DocumentListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=self.session, scope="PROJECT",
                    project_id=self.project, page_size=25,
                ), self.document)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
