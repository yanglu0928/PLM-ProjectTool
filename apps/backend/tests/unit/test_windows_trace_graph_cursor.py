import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hmac
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

from plm_assistant.entrypoints.windows_trace_graph_cursor import (
    TRACE_GRAPH_CURSOR_KEY_REF, ProductionTraceGraphCursorStartupError,
    create_windows_trace_graph_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    SecretKeyLifecycleError, provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.trace.application.query_bounded_graph import TraceBoundedGraphQuery
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class Resolver:
    def __init__(self, key):
        self.key, self.refs = key, []

    def __bool__(self):
        return False

    def resolve_key(self, ref):
        self.refs.append(ref)
        return self.key


class WindowsTraceGraphCursorTests(unittest.TestCase):
    def binding(self):
        project = uuid4()
        root = TraceVersionRef("document", "DOC-02", uuid4(), uuid4(),
                               "PROJECT", project)
        return TraceBoundedGraphQuery(b"s" * 32, uuid4(), project,
                                      root, "DOWNSTREAM"), datetime.now(timezone.utc)

    def test_exact_read_only_ref_and_falsy_resolver(self):
        resolver = Resolver(b"t" * 32)
        codec = create_windows_trace_graph_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [TRACE_GRAPH_CURSOR_KEY_REF])
        query, now = self.binding()
        token = codec.encode(query=query, page_size=1, next_index=1,
                             graph_digest="a" * 64, now=now)
        self.assertEqual(codec.decode(token, query=query, page_size=1, now=now),
                         (1, "a" * 64))

    def test_missing_invalid_and_provider_error_fail_closed(self):
        for key in (None, b"short", bytearray(b"t" * 32)):
            resolver = Resolver(key)
            with self.assertRaisesRegex(ProductionTraceGraphCursorStartupError,
                                        "^Trace graph cursor key unavailable$"):
                create_windows_trace_graph_cursor_codec(resolver=resolver)
            self.assertEqual(resolver.refs, [TRACE_GRAPH_CURSOR_KEY_REF])

        class Broken:
            def resolve_key(self, _ref):
                raise RuntimeError("private credential path")

        with self.assertRaises(ProductionTraceGraphCursorStartupError) as caught:
            create_windows_trace_graph_cursor_codec(resolver=Broken())
        self.assertNotIn("private", str(caught.exception))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_backup_and_restore_old_cursor(self):
        ref = "trace-graph-test-" + uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        self.assertIsNone(vault.resolve_key(ref))
        passphrase = "synthetic trace cursor recovery passphrase, not operator material"

        class Remapped:
            def resolve_key(self, key_ref):
                if key_ref != TRACE_GRAPH_CURSOR_KEY_REF:
                    raise ValueError()
                return vault.resolve_key(ref)

        with tempfile.TemporaryDirectory(prefix="plm-trace-graph-key-test-") as directory:
            backup = Path(directory) / "trace-graph-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase=passphrase, provider=vault)
                key = vault.resolve_key(ref)
                self.assertTrue(type(key) is bytes and len(key) == 32)
                self.assertNotIn(key.hex(), backup.read_text(encoding="utf-8"))
                codec = create_windows_trace_graph_cursor_codec(resolver=Remapped())
                query, now = self.binding()
                token = codec.encode(query=query, page_size=1, next_index=1,
                                     graph_digest="b" * 64, now=now)
                with self.assertRaises(SecretKeyLifecycleError):
                    restore_backup(backup_path=backup, passphrase=passphrase,
                                   provider=vault)
                self.assertTrue(hmac.compare_digest(vault.resolve_key(ref), key))
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                with self.assertRaises(ProductionTraceGraphCursorStartupError):
                    create_windows_trace_graph_cursor_codec(resolver=Remapped())
                with self.assertRaises(SecretKeyLifecycleError):
                    restore_backup(backup_path=backup,
                                   passphrase="synthetic wrong recovery passphrase",
                                   provider=vault)
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(backup_path=backup,
                                                passphrase=passphrase, provider=vault), ref)
                restored = create_windows_trace_graph_cursor_codec(resolver=Remapped())
                self.assertEqual(restored.decode(token, query=query, page_size=1,
                                                 now=now), (1, "b" * 64))
                self.assertTrue(hmac.compare_digest(vault.resolve_key(ref), key))
            finally:
                library.CredDeleteW(target, 1, 0)
        self.assertIsNone(vault.resolve_key(ref))


if __name__ == "__main__":
    unittest.main()
