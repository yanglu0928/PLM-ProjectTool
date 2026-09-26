from __future__ import annotations

import ctypes
import hashlib
import secrets
import sys
import tempfile
import unittest
from ctypes import wintypes
from pathlib import Path
from uuid import UUID, uuid4

from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.platform.application.system_actor import SystemActorUnavailable
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    SecretKeyLifecycleError, provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.windows_system_actor import WORKER_SYSTEM_ACTOR_KEY_REF


class Resolver:
    def __init__(self, material):
        self.material = material
        self.calls = []

    def resolve_key(self, ref):
        self.calls.append(ref)
        if isinstance(self.material, Exception):
            raise self.material
        return self.material


class WindowsSystemActorTests(unittest.TestCase):
    def test_fixed_reference_domain_and_stable_nonzero_identity(self):
        material = bytes(range(32))
        resolver = Resolver(material)
        actor = create_windows_system_actor(resolver=resolver)
        expected = UUID(bytes=hashlib.sha256(
            b"PLM-WORKER-SYSTEM-ACTOR-V1\x00" + material,
        ).digest()[:16])
        self.assertNotEqual(expected.int, 0)
        for _ in range(3):
            self.assertEqual(actor.assert_current(), expected)
        self.assertEqual(create_windows_system_actor(resolver=resolver).assert_current(), expected)
        self.assertEqual(resolver.calls, [WORKER_SYSTEM_ACTOR_KEY_REF] * 6)
        self.assertNotEqual(expected, UUID(bytes=hashlib.sha256(material).digest()[:16]))
        self.assertNotIn(material, actor.__dict__.values())

    def test_startup_invalid_or_missing_source_is_safe(self):
        for material in (None, b"", b"x" * 31, b"x" * 33, "x" * 32,
                         bytearray(32), True, RuntimeError("unsafe path and material")):
            with self.subTest(kind=type(material).__name__):
                with self.assertRaises(SystemActorUnavailable) as caught:
                    create_windows_system_actor(resolver=Resolver(material))
                self.assertEqual(str(caught.exception), "system actor unavailable")
                self.assertEqual(caught.exception.code, "SYSTEM_ACTOR_UNAVAILABLE")
                self.assertTrue(caught.exception.__suppress_context__)

    def test_every_use_rechecks_loss_change_and_recovery(self):
        original = b"a" * 32
        resolver = Resolver(original)
        actor = create_windows_system_actor(resolver=resolver)
        identity = actor.assert_current()
        for unavailable in (None, b"b" * 32, b"short", RuntimeError("unsafe source")):
            resolver.material = unavailable
            with self.assertRaises(SystemActorUnavailable):
                actor.assert_current()
            resolver.material = original
            self.assertEqual(actor.assert_current(), identity)

    @unittest.skipUnless(sys.platform == "win32", "Windows Vault only")
    def test_real_vault_loss_wrong_password_restore_and_replacement(self):
        ref = "system-actor-test-" + uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        vault = WindowsSecretKeyProvider()
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        self.assertIsNone(vault.resolve_key(ref))
        passphrase = secrets.token_urlsafe(48)
        calls = []

        class TestVaultMapping:
            def resolve_key(self, requested_ref):
                calls.append(requested_ref)
                if requested_ref != WORKER_SYSTEM_ACTOR_KEY_REF:
                    raise AssertionError("unexpected reference")
                return vault.resolve_key(ref)

        with tempfile.TemporaryDirectory(prefix="PLM-system-actor-test-") as directory:
            backup = Path(directory) / "synthetic-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup, passphrase=passphrase, provider=vault)
                actor = create_windows_system_actor(resolver=TestVaultMapping())
                identity = actor.assert_current()
                with self.assertRaises(RuntimeError):
                    vault.install_new(ref, secrets.token_bytes(32))
                self.assertEqual(actor.assert_current(), identity)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                with self.assertRaises(SystemActorUnavailable):
                    actor.assert_current()
                with self.assertRaises(SystemActorUnavailable):
                    create_windows_system_actor(resolver=TestVaultMapping())
                with self.assertRaises(SecretKeyLifecycleError):
                    restore_backup(backup_path=backup, passphrase=secrets.token_urlsafe(48), provider=vault)
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup, passphrase=passphrase, provider=vault,
                ), ref)
                self.assertEqual(actor.assert_current(), identity)
                self.assertEqual(create_windows_system_actor(resolver=TestVaultMapping()).assert_current(), identity)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                vault.install_new(ref, secrets.token_bytes(32))
                with self.assertRaises(SystemActorUnavailable):
                    actor.assert_current()
                self.assertNotEqual(create_windows_system_actor(resolver=TestVaultMapping()).assert_current(), identity)
                self.assertEqual(set(calls), {WORKER_SYSTEM_ACTOR_KEY_REF})
            finally:
                library.CredDeleteW(target, 1, 0)
        self.assertIsNone(vault.resolve_key(ref))


if __name__ == "__main__":
    unittest.main()
