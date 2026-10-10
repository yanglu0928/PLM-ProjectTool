"""PROJECT Reference list cursor current-account key and recovery tests."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference_cursor import (
    GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF,
    REFERENCE_LIST_CURSOR_KEY_REF, ProductionReferenceCursorStartupError,
    create_windows_global_reference_list_cursor_codec,
    create_windows_project_reference_list_cursor_codec,
    PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF,
    create_windows_project_global_reference_candidate_cursor_codec,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import GlobalReferenceCandidateCursorCodec


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsReferenceCursorTests(unittest.TestCase):
    def test_project_global_candidate_uses_distinct_required_key(self):
        self.assertNotEqual(PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF,
                            REFERENCE_LIST_CURSOR_KEY_REF)
        self.assertNotEqual(PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF,
                            GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF)
        resolver = Resolver(b"c" * 32)
        codec = create_windows_project_global_reference_candidate_cursor_codec(
            resolver=resolver)
        self.assertIsInstance(codec, GlobalReferenceCandidateCursorCodec)
        self.assertEqual([PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF],
                         resolver.calls)
        for bad in (None, b"short", b"c" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionReferenceCursorStartupError):
                create_windows_project_global_reference_candidate_cursor_codec(
                    resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_project_global_candidate_temporary_vault_backup_restore(self):
        ref = "global-candidate-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, root = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "global-candidate-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic candidate cursor recovery passphrase",
                    provider=vault)
                before = GlobalReferenceCandidateCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    page_size=20, after_root_id=root)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic candidate cursor recovery passphrase",
                    provider=vault), ref)
                after = GlobalReferenceCandidateCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, page_size=20), root)
            finally:
                library.CredDeleteW(target, 1, 0)

    def test_global_dedicated_key_required(self):
        self.assertNotEqual(REFERENCE_LIST_CURSOR_KEY_REF,
                            GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF)
        resolver = Resolver(b"g" * 32)
        codec = create_windows_global_reference_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, GlobalReferenceListCursorCodec)
        self.assertEqual([GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF], resolver.calls)
        for bad in (None, b"short", b"g" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionReferenceCursorStartupError):
                create_windows_global_reference_list_cursor_codec(
                    resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_global_temporary_vault_loss_and_backup_restore(self):
        ref = "global-reference-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        reference = uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "global-reference-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic global reference cursor backup passphrase",
                    provider=vault)
                before = GlobalReferenceListCursorCodec(vault.resolve_key(ref))
                token = before.encode(session_token=b"s" * 32, page_size=25,
                                      reference_solution_id=reference)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic global reference cursor backup passphrase",
                    provider=vault), ref)
                after = GlobalReferenceListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32, page_size=25), reference)
            finally:
                library.CredDeleteW(target, 1, 0)

    def test_dedicated_key_required(self):
        self.assertNotEqual("document-list-cursor-v1", REFERENCE_LIST_CURSOR_KEY_REF)
        resolver = Resolver(b"r" * 32)
        codec = create_windows_project_reference_list_cursor_codec(resolver=resolver)
        self.assertIsInstance(codec, ReferenceListCursorCodec)
        self.assertEqual([REFERENCE_LIST_CURSOR_KEY_REF], resolver.calls)
        for bad in (None, b"short", b"r" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionReferenceCursorStartupError):
                create_windows_project_reference_list_cursor_codec(
                    resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_backup_restore(self):
        ref = "reference-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, reference = uuid.uuid4(), uuid.uuid4()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "reference-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic reference cursor backup passphrase long enough",
                    provider=vault)
                before = ReferenceListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    page_size=25, reference_solution_id=reference)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic reference cursor backup passphrase long enough",
                    provider=vault), ref)
                after = ReferenceListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, page_size=25), reference)
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
