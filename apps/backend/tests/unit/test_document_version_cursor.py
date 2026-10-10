from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_document_version_cursor import (
    DOCUMENT_VERSION_CURSOR_KEY_REF, ProductionVersionCursorStartupError,
    create_windows_document_version_cursor_codec,
)
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new, restore_backup
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


class Resolver:
    def __init__(self, key):
        self.key = key
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.key


class VersionListCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = VersionListCursorCodec(b"v" * 32)
        self.session = b"s" * 32
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()

    def token(self, *, scope="PROJECT", project_id=None, document_id=None,
              page_size=25, before_version_no=3):
        return self.codec.encode(
            session_token=self.session, scope=scope,
            project_id=self.project if project_id is None and scope == "PROJECT" else project_id,
            document_id=document_id or self.document,
            page_size=page_size, before_version_no=before_version_no,
        )

    def test_project_and_global_roundtrip(self):
        for scope, project_id in (("PROJECT", self.project), ("GLOBAL", None)):
            with self.subTest(scope=scope):
                token = self.token(scope=scope, project_id=project_id)
                self.assertEqual(self.codec.decode(
                    token, session_token=self.session, scope=scope,
                    project_id=project_id, document_id=self.document, page_size=25,
                ), 3)

    def test_tamper_and_cross_context_fail_closed(self):
        token = self.token()
        for changed in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                        token + "x", "bad"):
            with self.subTest(changed=changed), self.assertRaises(ApplicationError):
                self.codec.decode(changed, session_token=self.session, scope="PROJECT",
                                  project_id=self.project, document_id=self.document,
                                  page_size=25)
        for session, scope, project, document, size in (
            (b"x" * 32, "PROJECT", self.project, self.document, 25),
            (self.session, "PROJECT", uuid.uuid4(), self.document, 25),
            (self.session, "GLOBAL", None, self.document, 25),
            (self.session, "PROJECT", self.project, uuid.uuid4(), 25),
            (self.session, "PROJECT", self.project, self.document, 50),
        ):
            with self.subTest(scope=scope, project=project, document=document), self.assertRaises(ApplicationError):
                self.codec.decode(token, session_token=session, scope=scope,
                                  project_id=project, document_id=document,
                                  page_size=size)

    def test_invalid_key_and_position_rejected(self):
        with self.assertRaises(ValueError):
            VersionListCursorCodec(b"short")
        for project, document, size, before in (
            (None, self.document, 25, 3),
            (self.project, uuid.UUID(int=0), 25, 3),
            (self.project, self.document, 0, 3),
            (self.project, self.document, 25, 0),
            (self.project, self.document, 25, True),
        ):
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.codec.encode(session_token=self.session, scope="PROJECT",
                                  project_id=project, document_id=document,
                                  page_size=size, before_version_no=before)

    def test_windows_key_is_dedicated_and_required(self):
        resolver = Resolver(b"k" * 32)
        codec = create_windows_document_version_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, VersionListCursorCodec)
        self.assertEqual(resolver.calls, [DOCUMENT_VERSION_CURSOR_KEY_REF])
        with self.assertRaises(ProductionVersionCursorStartupError):
            create_windows_document_version_cursor_codec(resolver=Resolver(None))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_windows_vault_loss_and_backup_restore_preserves_cursor(self):
        ref = "version-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "version-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic version cursor backup passphrase with enough length",
                    provider=vault,
                )
                before = VersionListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=self.session, scope="PROJECT",
                    project_id=self.project, document_id=self.document,
                    page_size=25, before_version_no=3,
                )
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic version cursor backup passphrase with enough length",
                    provider=vault,
                ), ref)
                after = VersionListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=self.session, scope="PROJECT",
                    project_id=self.project, document_id=self.document,
                    page_size=25,
                ), 3)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
