import ctypes
from ctypes import wintypes
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4
from plm_assistant.entrypoints.windows_audit_list_cursor import AUDIT_CURSOR_KEY_REF,ProductionAuditCursorStartupError,create_windows_audit_cursor_codec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.application.queries.audit_query import AuditSearch,AuditPosition
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new,restore_backup


class Resolver:
    def __init__(self,key):self.key,self.refs=key,[]
    def resolve_key(self,ref):self.refs.append(ref);return self.key


class AuditCursorWindowsTests(unittest.TestCase):
    def binding(self):
        now=datetime.now(timezone.utc)
        return dict(session_token=b"s"*32,actor_id=uuid4(),project_id=uuid4(),search=AuditSearch(now-timedelta(days=1),now)),AuditPosition(now-timedelta(seconds=1),uuid4())

    def test_dedicated_read_only_ref_roundtrip(self):
        resolver=Resolver(b"k"*32);codec=create_windows_audit_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs,[AUDIT_CURSOR_KEY_REF])
        args,pos=self.binding();token=codec.encode(**args,position=pos)
        self.assertEqual(codec.decode(token,**args).after,pos)

    def test_missing_wrong_shape_and_provider_exception_fail_closed(self):
        for key in (None,b"short",bytearray(b"k"*32)):
            with self.assertRaisesRegex(ProductionAuditCursorStartupError,"^audit cursor key unavailable$"):
                create_windows_audit_cursor_codec(resolver=Resolver(key))
        class Broken:
            def resolve_key(self,ref):raise RuntimeError("sensitive provider detail")
        with self.assertRaises(ProductionAuditCursorStartupError) as exc:
            create_windows_audit_cursor_codec(resolver=Broken())
        self.assertNotIn("sensitive",str(exc.exception))

    @unittest.skipUnless(sys.platform=="win32","Windows Credential Manager only")
    def test_current_account_temporary_vault_loss_restore_old_cursor(self):
        ref="audit-cursor-test-"+uuid4().hex
        target="PLMProjectTool/SecretKey/"+ref
        library=ctypes.WinDLL("Advapi32",use_last_error=True)
        library.CredDeleteW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD]
        library.CredDeleteW.restype=wintypes.BOOL
        vault=WindowsSecretKeyProvider()
        password="synthetic audit recovery passphrase with sufficient length"
        class Remapped:
            def resolve_key(self,key_ref):
                assert key_ref==AUDIT_CURSOR_KEY_REF
                return vault.resolve_key(ref)
        with tempfile.TemporaryDirectory() as directory:
            backup=Path(directory)/"audit-recovery.json"
            try:
                provision_new(key_ref=ref,backup_path=backup,passphrase=password,provider=vault)
                key=vault.resolve_key(ref)
                self.assertNotIn(key.hex(),backup.read_text(encoding="utf-8"))
                codec=create_windows_audit_cursor_codec(resolver=Remapped())
                args,pos=self.binding();token=codec.encode(**args,position=pos)
                self.assertTrue(library.CredDeleteW(target,1,0))
                with self.assertRaises(ProductionAuditCursorStartupError):create_windows_audit_cursor_codec(resolver=Remapped())
                self.assertEqual(restore_backup(backup_path=backup,passphrase=password,provider=vault),ref)
                restored=create_windows_audit_cursor_codec(resolver=Remapped())
                self.assertEqual(restored.decode(token,**args).after,pos)
                self.assertEqual(vault.resolve_key(ref),key)
            finally:
                library.CredDeleteW(target,1,0)
        self.assertIsNone(vault.resolve_key(ref))


if __name__=="__main__":unittest.main()
