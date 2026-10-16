from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_document_upload_token import (
    DOCUMENT_UPLOAD_TOKEN_KEY_REF, ProductionUploadTokenStartupError,
    create_windows_document_upload_token_issuer,
)
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PASSPHRASE = "synthetic document upload recovery passphrase with enough length"


class _Resolver:
    def __init__(self, key):
        self.key = key
        self.refs = []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        return self.key


class WindowsDocumentUploadTokenTests(unittest.TestCase):
    def test_dedicated_ref_and_missing_key_fail_closed(self):
        resolver = _Resolver(b"u" * 32)
        issuer = create_windows_document_upload_token_issuer(resolver=resolver)
        self.assertEqual(resolver.refs, [DOCUMENT_UPLOAD_TOKEN_KEY_REF])
        args = dict(upload_id=uuid.uuid4(), actor_id=uuid.uuid4(),
                    scope="GLOBAL", project_id=None)
        self.assertEqual(issuer.issue(**args), issuer.issue(**args))
        resolver.key = None
        with self.assertRaises(RuntimeError):
            issuer.issue(**args)
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(ProductionUploadTokenStartupError):
                create_windows_document_upload_token_issuer(resolver=_Resolver(key))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_vault_loss_and_backup_restore_preserves_token(self):
        ref = "upload-token-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "upload-token-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=_PASSPHRASE, provider=vault)
                issuer = HmacUploadTokenIssuer(provider=vault, key_ref=ref)
                args = dict(upload_id=uuid.uuid4(), actor_id=uuid.uuid4(),
                            scope="PROJECT", project_id=uuid.uuid4())
                original = issuer.issue(**args)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                with self.assertRaises(RuntimeError):
                    issuer.issue(**args)
                self.assertEqual(restore_backup(backup_path=backup,
                                                passphrase=_PASSPHRASE,
                                                provider=vault), ref)
                self.assertEqual(issuer.issue(**args), original)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
