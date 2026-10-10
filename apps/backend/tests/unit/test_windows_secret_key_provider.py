from __future__ import annotations

import ctypes
import sys
import unittest
import uuid
from ctypes import wintypes
from unittest.mock import patch

from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretState,
)
from plm_assistant.modules.platform.infrastructure.secret_crypto import (
    AesGcmSecretCrypto, SecretCryptoError,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    _Credential,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


class WindowsSecretKeyProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = WindowsSecretKeyProvider()

    def test_invalid_reference_and_platform_fail_closed(self) -> None:
        for ref in ("", "../other", "other/key", "bad\x00name", "a" * 81, 123):
            with self.subTest(ref=ref):
                self.assertIsNone(self.provider.resolve_key(ref))
        with patch(
            "plm_assistant.modules.platform.infrastructure.windows_secret_key_provider.sys.platform",
            "linux",
        ):
            self.assertIsNone(self.provider.resolve_key("valid-key"))
        with self.assertRaises(SecretCryptoError):
            AesGcmSecretCrypto(self.provider, key_ref="missing-" + uuid.uuid4().hex).encrypt(
                secret_ref=SecretRef(uuid.uuid4()), purpose=SecretPurpose.AI_PROVIDER_KEY,
                consumer=SecretConsumer.AI_PROVIDER_ADAPTER, version_no=1,
                plaintext=bytearray(b"synthetic"),
            )

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_current_account_vault_round_trip(self) -> None:
        ref = "test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        key = bytes(range(32))  # Synthetic test-only material, never a deployment key.
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        library.CredWriteW.restype = wintypes.BOOL
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        self.assertIsNone(self.provider.resolve_key(ref))
        try:
            for material in (key, b"short"):
                blob = (ctypes.c_ubyte * len(material)).from_buffer_copy(material)
                credential = _Credential()
                credential.Type = 1
                credential.TargetName = target
                credential.CredentialBlobSize = len(material)
                credential.CredentialBlob = blob
                credential.Persist = 2
                credential.UserName = "plm-project-tool-test"
                self.assertTrue(library.CredWriteW(ctypes.byref(credential), 0))
                self.assertEqual(self.provider.resolve_key(ref), key if len(material) == 32 else None)
                if len(material) == 32:
                    crypto = AesGcmSecretCrypto(self.provider, key_ref=ref)
                    secret_ref = SecretRef(uuid.uuid4())
                    draft = crypto.encrypt(
                        secret_ref=secret_ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
                        consumer=SecretConsumer.AI_PROVIDER_ADAPTER, version_no=1,
                        plaintext=bytearray(b"synthetic-value"),
                    )
                    envelope = SecretEnvelope(
                        secret_ref, SecretPurpose.AI_PROVIDER_KEY, SecretState.ACTIVE,
                        SecretConsumer.AI_PROVIDER_ADAPTER, 1,
                        draft.encrypted_payload, draft.encryption_metadata, draft.key_provider_ref,
                    )
                    self.assertEqual(crypto.decrypt(envelope), bytearray(b"synthetic-value"))
        finally:
            library.CredDeleteW(target, 1, 0)
        self.assertIsNone(self.provider.resolve_key(ref))


if __name__ == "__main__":
    unittest.main()
