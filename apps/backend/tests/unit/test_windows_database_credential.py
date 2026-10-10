from __future__ import annotations

import ctypes
import sys
import unittest
import uuid
from ctypes import wintypes
from unittest.mock import patch

from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    DatabaseCredentialError,
    read_database_url,
    write_database_url,
)


class WindowsDatabaseCredentialTests(unittest.TestCase):
    def test_rejects_bad_url_and_target_without_leak(self) -> None:
        synthetic = "synthetic-password-not-a-secret"
        for url, target in (
            (f"sqlite:///{synthetic}", "test"),
            (f"postgresql+psycopg://user:{synthetic}@localhost/db", "bad\x00target"),
            ("postgresql+psycopg://user@localhost/db", "test"),
        ):
            with self.subTest(target=target):
                with self.assertRaises(DatabaseCredentialError) as captured:
                    write_database_url(url, target=target)
                self.assertNotIn(synthetic, str(captured.exception))

    def test_unavailable_platform_fails_closed(self) -> None:
        with patch(
            "plm_assistant.modules.platform.infrastructure.windows_database_credential.sys.platform",
            "linux",
        ):
            with self.assertRaises(DatabaseCredentialError):
                read_database_url(target="PLMProjectTool/Test")

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager only")
    def test_windows_round_trip_and_missing_target(self) -> None:
        target = f"PLMProjectTool/Test-{uuid.uuid4()}"
        first = "postgresql+psycopg://test:synthetic-one@localhost/test_db"
        second = "postgresql+psycopg://test:synthetic-two@localhost/test_db"
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        try:
            with self.assertRaises(DatabaseCredentialError):
                read_database_url(target=target)
            write_database_url(first, target=target)
            self.assertEqual(read_database_url(target=target), first)
            write_database_url(second, target=target)
            self.assertEqual(read_database_url(target=target), second)
        finally:
            # Only this UUID-scoped synthetic item is removed.
            library.CredDeleteW(target, 1, 0)


if __name__ == "__main__":
    unittest.main()
