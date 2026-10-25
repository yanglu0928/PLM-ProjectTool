from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_document_parse_cursor import (
    DOCUMENT_PARSE_CURSOR_KEY_REF, ProductionParseCursorStartupError,
    create_windows_document_parse_cursor_codec,
)
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


class Resolver:
    def __init__(self, key):
        self.key = key
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.key


class ParseListCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = ParseListCursorCodec(b"p" * 32)
        self.session = b"s" * 32
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()
        self.version = uuid.uuid4()
        self.before = (datetime(2026, 9, 26, tzinfo=timezone.utc), uuid.uuid4())

    def encode(self):
        return self.codec.encode(
            session_token=self.session, scope="PROJECT", project_id=self.project,
            document_id=self.document, document_version_id=self.version,
            page_size=25, before=self.before,
        )

    def test_roundtrip_context_and_tamper(self):
        token = self.encode()
        self.assertEqual(self.codec.decode(
            token, session_token=self.session, scope="PROJECT",
            project_id=self.project, document_id=self.document,
            document_version_id=self.version, page_size=25,
        ), self.before)
        for session, project, version, size, value in (
            (b"x" * 32, self.project, self.version, 25, token),
            (self.session, uuid.uuid4(), self.version, 25, token),
            (self.session, self.project, uuid.uuid4(), 25, token),
            (self.session, self.project, self.version, 50, token),
            (self.session, self.project, self.version, 25, token + "x"),
        ):
            with self.subTest(value=value), self.assertRaises(ApplicationError):
                self.codec.decode(
                    value, session_token=session, scope="PROJECT",
                    project_id=project, document_id=self.document,
                    document_version_id=version, page_size=size,
                )

    def test_dedicated_windows_source_fails_closed(self):
        resolver = Resolver(b"k" * 32)
        self.assertIsInstance(create_windows_document_parse_cursor_codec(
            resolver=resolver), ParseListCursorCodec)
        self.assertEqual(resolver.calls, [DOCUMENT_PARSE_CURSOR_KEY_REF])
        with self.assertRaises(ProductionParseCursorStartupError):
            create_windows_document_parse_cursor_codec(resolver=Resolver(None))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_windows_vault_loss_and_backup_restore(self):
        ref = "parse-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "parse-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic parse cursor backup passphrase with enough length",
                    provider=vault,
                )
                before = ParseListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=self.session, scope="PROJECT",
                    project_id=self.project, document_id=self.document,
                    document_version_id=self.version, page_size=25,
                    before=self.before,
                )
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic parse cursor backup passphrase with enough length",
                    provider=vault,
                ), ref)
                after = ParseListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=self.session, scope="PROJECT",
                    project_id=self.project, document_id=self.document,
                    document_version_id=self.version, page_size=25,
                ), self.before)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
