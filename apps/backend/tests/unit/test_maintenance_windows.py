import sys
import unittest
from unittest.mock import patch

from plm_assistant.entrypoints.maintenance_windows import main


class MaintenanceWindowsCliTests(unittest.TestCase):
    def test_rejects_non_windows_or_non_interactive_before_vault_access(self):
        with patch.object(sys, "platform", "linux"), patch(
            "plm_assistant.entrypoints.maintenance_windows.read_database_url"
        ) as vault:
            self.assertEqual(main(), 2)
            vault.assert_not_called()

    def test_rejects_secret_arguments_before_vault_access(self):
        with patch.object(sys, "platform", "win32"), patch.object(
            sys, "argv", ["maintenance", "enter", "0", "unexpected-extra"]
        ), patch("plm_assistant.entrypoints.maintenance_windows.read_database_url") as vault:
            self.assertEqual(main(), 2)
            vault.assert_not_called()


if __name__ == "__main__":
    unittest.main()
