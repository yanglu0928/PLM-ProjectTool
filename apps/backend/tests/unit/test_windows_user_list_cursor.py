import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hmac
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4
from plm_assistant.entrypoints.windows_user_list_cursor import USER_LIST_CURSOR_KEY_REF, ProductionUserListCursorStartupError, create_windows_user_list_cursor_codec
from plm_assistant.modules.auth.application.user_list import UserListQuery
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new, restore_backup, SecretKeyLifecycleError


class Resolver:
    def __init__(self, key): self.key, self.refs = key, []
    def __bool__(self): return False
    def resolve_key(self, ref): self.refs.append(ref); return self.key


class WindowsUserListCursorTests(unittest.TestCase):
    def binding(self):
        return UserListQuery(b's' * 32, uuid4(), 1), (datetime.now(timezone.utc), uuid4())

    def test_dedicated_read_only_ref_falsy_port_and_roundtrip(self):
        resolver = Resolver(b'k' * 32)
        codec = create_windows_user_list_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [USER_LIST_CURSOR_KEY_REF])
        query, position = self.binding(); token = codec.encode(query=query, before=position)
        self.assertEqual(codec.decode(token, query=query), position)

    def test_missing_shape_provider_exception_static_no_fallback(self):
        for key in (None, b'short', bytearray(b'k' * 32)):
            resolver = Resolver(key)
            with self.assertRaisesRegex(ProductionUserListCursorStartupError, '^User list cursor key unavailable$'):
                create_windows_user_list_cursor_codec(resolver=resolver)
            self.assertEqual(resolver.refs, [USER_LIST_CURSOR_KEY_REF])
        class Broken:
            def resolve_key(self, ref): raise RuntimeError('private provider SQL path')
        with self.assertRaises(ProductionUserListCursorStartupError) as cm:
            create_windows_user_list_cursor_codec(resolver=Broken())
        self.assertNotIn('private', str(cm.exception))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows Credential Manager only')
    def test_actual_temporary_vault_loss_wrong_password_restore_old_ciphertext(self):
        ref = 'user-list-test-' + uuid4().hex
        target = 'PLMProjectTool/SecretKey/' + ref
        library = ctypes.WinDLL('Advapi32', use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        self.assertIsNone(vault.resolve_key(ref))  # never remove a pre-existing target
        passphrase = 'synthetic user cursor recovery passphrase, not operator material'
        class Remapped:
            def resolve_key(self, key_ref):
                if key_ref != USER_LIST_CURSOR_KEY_REF: raise ValueError()
                return vault.resolve_key(ref)
        with tempfile.TemporaryDirectory(prefix='plm-user-list-key-test-') as directory:
            backup = Path(directory) / 'user-list-recovery.json'
            try:
                provision_new(key_ref=ref, backup_path=backup, passphrase=passphrase, provider=vault)
                key = vault.resolve_key(ref)
                self.assertTrue(type(key) is bytes and len(key) == 32)
                self.assertNotIn(key.hex(), backup.read_text(encoding='utf-8'))
                codec = create_windows_user_list_cursor_codec(resolver=Remapped())
                query, position = self.binding(); token = codec.encode(query=query, before=position)
                with self.assertRaises(SecretKeyLifecycleError):
                    restore_backup(backup_path=backup, passphrase=passphrase, provider=vault)
                self.assertTrue(hmac.compare_digest(vault.resolve_key(ref), key))
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                with self.assertRaises(ProductionUserListCursorStartupError):
                    create_windows_user_list_cursor_codec(resolver=Remapped())
                with self.assertRaises(SecretKeyLifecycleError):
                    restore_backup(backup_path=backup, passphrase='synthetic wrong recovery passphrase', provider=vault)
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup, passphrase=passphrase, provider=vault), ref)
                restored = create_windows_user_list_cursor_codec(resolver=Remapped())
                self.assertEqual(restored.decode(token, query=query), position)
                self.assertTrue(hmac.compare_digest(vault.resolve_key(ref), key))
            finally:
                library.CredDeleteW(target, 1, 0)
        self.assertIsNone(vault.resolve_key(ref))
