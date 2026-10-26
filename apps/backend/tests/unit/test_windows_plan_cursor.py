"""Plan cursor current-account key, fail-closed and recovery."""

from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_plan_cursor import (
    PLAN_LIST_CURSOR_KEY_REF, ProductionPlanCursorStartupError,
    create_windows_plan_list_cursor_codec,
    create_windows_plan_version_list_cursor_codec,
    create_windows_plan_version_wbs_cursor_codec,
)
from plm_assistant.entrypoints.windows_solution_outline_cursor import OUTLINE_LIST_CURSOR_KEY_REF
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.plan.api.wbs_list_cursor import PlanVersionWbsCursorCodec
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec


class Resolver:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_key(self, key_ref):
        self.calls.append(key_ref)
        return self.value


class WindowsPlanCursorTests(unittest.TestCase):
    def test_dedicated_key_and_fail_closed(self):
        self.assertNotEqual(PLAN_LIST_CURSOR_KEY_REF, OUTLINE_LIST_CURSOR_KEY_REF)
        resolver = Resolver(b"p" * 32)
        self.assertIsInstance(create_windows_plan_list_cursor_codec(
            resolver=resolver), PlanListCursorCodec)
        self.assertEqual([PLAN_LIST_CURSOR_KEY_REF], resolver.calls)
        self.assertIsInstance(create_windows_plan_version_wbs_cursor_codec(
            resolver=resolver), PlanVersionWbsCursorCodec)
        self.assertIsInstance(create_windows_plan_version_list_cursor_codec(
            resolver=resolver), PlanVersionListCursorCodec)
        self.assertEqual([PLAN_LIST_CURSOR_KEY_REF] * 3,
                         resolver.calls)
        for bad in (None, b"short", b"p" * 31):
            with self.subTest(bad=bad), self.assertRaises(
                    ProductionPlanCursorStartupError):
                create_windows_plan_list_cursor_codec(resolver=Resolver(bad))
            with self.subTest(wbs_bad=bad), self.assertRaises(
                    ProductionPlanCursorStartupError):
                create_windows_plan_version_wbs_cursor_codec(resolver=Resolver(bad))
            with self.subTest(version_bad=bad), self.assertRaises(
                    ProductionPlanCursorStartupError):
                create_windows_plan_version_list_cursor_codec(resolver=Resolver(bad))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_encrypted_backup_restore(self):
        ref = "plan-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        project, plan, version, item = (uuid.uuid4() for _ in range(4))
        when = datetime(2026, 10, 19, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "plan-cursor-recovery.json"
            try:
                provision_new(
                    key_ref=ref, backup_path=backup,
                    passphrase="synthetic plan cursor backup passphrase long enough",
                    provider=vault)
                before = PlanListCursorCodec(vault.resolve_key(ref))
                token = before.encode(
                    session_token=b"s" * 32, project_id=project,
                    page_size=25, created_at=when, plan_id=plan)
                wbs_before = PlanVersionWbsCursorCodec(vault.resolve_key(ref))
                wbs_token = wbs_before.encode(
                    session_token=b"s" * 32, project_id=project, plan_id=plan,
                    plan_version_id=version, page_size=10, ordinal=7,
                    wbs_item_id=item)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic plan cursor backup passphrase long enough",
                    provider=vault), ref)
                after = PlanListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(
                    token, session_token=b"s" * 32,
                    project_id=project, page_size=25), (when, plan))
                wbs_after = PlanVersionWbsCursorCodec(vault.resolve_key(ref))
                self.assertEqual(wbs_after.decode(
                    wbs_token, session_token=b"s" * 32,
                    project_id=project, plan_id=plan,
                    plan_version_id=version, page_size=10), (7, item))
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
