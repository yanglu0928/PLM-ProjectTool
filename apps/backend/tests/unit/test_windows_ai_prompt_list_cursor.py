from __future__ import annotations

import ctypes
import sys
import tempfile
import unittest
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.windows_ai_prompt_list_cursor import (
    AI_PROMPT_LIST_CURSOR_KEY_REF, ProductionAIPromptCursorStartupError,
    create_windows_ai_prompt_list_cursor_codec,
)
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    provision_new, restore_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


class FakeResolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key
        self.refs: list[str] = []

    def resolve_key(self, ref: str) -> bytes | None:
        self.refs.append(ref)
        return self.key


class AIPromptCursorWindowsTests(unittest.TestCase):
    def test_dedicated_ref_and_missing_key_fail_closed(self) -> None:
        resolver = FakeResolver(b"k" * 32)
        codec = create_windows_ai_prompt_list_cursor_codec(resolver=resolver)
        self.assertEqual(resolver.refs, [AI_PROMPT_LIST_CURSOR_KEY_REF])
        token = codec.encode(
            session_token=b"s" * 32, page_size=1,
            created_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            template_id=uuid.uuid4(),
        )
        self.assertIn(".", token)
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(ProductionAIPromptCursorStartupError):
                create_windows_ai_prompt_list_cursor_codec(resolver=FakeResolver(key))

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_temporary_vault_loss_and_backup_restore_preserves_cursor(self) -> None:
        ref = "ai-prompt-cursor-test-" + uuid.uuid4().hex
        target = "PLMProjectTool/SecretKey/" + ref
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        vault = WindowsSecretKeyProvider()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "prompt-cursor-recovery.json"
            try:
                provision_new(key_ref=ref, backup_path=backup,
                              passphrase="synthetic Prompt cursor recovery passphrase with enough length",
                              provider=vault)
                before = PromptListCursorCodec(vault.resolve_key(ref))
                position = uuid.uuid4()
                instant = datetime(2026, 10, 2, tzinfo=timezone.utc)
                token = before.encode(session_token=b"s" * 32, page_size=50,
                                      created_at=instant, template_id=position)
                self.assertTrue(library.CredDeleteW(target, 1, 0))
                self.assertIsNone(vault.resolve_key(ref))
                self.assertEqual(restore_backup(
                    backup_path=backup,
                    passphrase="synthetic Prompt cursor recovery passphrase with enough length",
                    provider=vault,
                ), ref)
                after = PromptListCursorCodec(vault.resolve_key(ref))
                self.assertEqual(after.decode(token, session_token=b"s" * 32,
                                              page_size=50), (instant, position))
            finally:
                library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
