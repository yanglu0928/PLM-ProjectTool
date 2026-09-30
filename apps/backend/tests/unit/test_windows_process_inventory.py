"""OS candidate reports are intentionally weaker than quiescence proof."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import PureWindowsPath
from unittest.mock import patch

from plm_assistant.entrypoints import process_inventory_windows as cli
from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
    ProcessObservation, WindowsProcessInventoryError, assess_processes,
)


SID = "S-1-5-21-100-200-300-400"


class WindowsProcessInventoryTests(unittest.TestCase):
    def test_account_root_and_module_candidates_without_clearance(self):
        processes = (
            ProcessObservation(1, "python.exe", SID, "C:\\Other\\python.exe",
                               "python -m other secret-password-do-not-print"),
            ProcessObservation(2, "python.exe", "S-1-5-18",
                               "C:\\PLMTool\\runtime\\python.exe", None),
            ProcessObservation(3, "python.exe", "S-1-5-18",
                               "D:\\Other\\python.exe",
                               "python -m plm_assistant.entrypoints.worker_windows config.yaml"),
            ProcessObservation(4, "pwsh.exe", SID, None,
                               "python -m plm_assistant.entrypoints.process_inventory_windows"),
            ProcessObservation(5, "notepad.exe", "S-1-5-18",
                               "C:\\Windows\\notepad.exe", "notepad.exe"),
            ProcessObservation(6, "python.exe", "S-1-5-18",
                               "D:\\Other\\python.exe",
                               "python -m plm_assistant.entrypoints.service_windows API C:/config.yaml"),
        )
        result = assess_processes(processes, deployment_sid=SID,
            runtime_root=PureWindowsPath("C:/PLMTool"), observer_pid=4)
        self.assertEqual(result.classification, "DIAGNOSTIC_ONLY")
        self.assertEqual([(item.pid, item.reasons) for item in result.findings], [
            (1, ("DEPLOYMENT_ACCOUNT",)),
            (2, ("RUNTIME_ROOT",)),
            (3, ("PRODUCT_ENTRYPOINT",)),
            (6, ("PRODUCT_ENTRYPOINT",)),
        ])
        self.assertEqual(result.unreadable_processes, 1)

    def test_unknown_and_invalid_input_fail_conservatively(self):
        processes = (ProcessObservation(8, "python.exe", None, None, None),)
        result = assess_processes(processes, deployment_sid=SID,
            runtime_root=PureWindowsPath("C:/PLMTool"), observer_pid=9)
        self.assertEqual((len(result.findings), result.unreadable_processes), (0, 1))
        for root in (PureWindowsPath("C:/"), PureWindowsPath("relative"),
                     PureWindowsPath("//server/share/PLMTool")):
            with self.assertRaises(WindowsProcessInventoryError):
                assess_processes(processes, deployment_sid=SID,
                                 runtime_root=root, observer_pid=9)
        with self.assertRaises(WindowsProcessInventoryError):
            assess_processes(processes, deployment_sid="not-a-sid",
                             runtime_root=PureWindowsPath("C:/PLMTool"), observer_pid=9)

    def test_cli_never_emits_command_line_or_backup_permission(self):
        output = io.StringIO()
        processes = (ProcessObservation(42, "python.exe", SID,
            "C:\\PLMTool\\runtime\\python.exe", "private-password-do-not-print"),)
        with patch.object(cli.sys, "platform", "win32"), \
             patch.object(cli.sys, "argv", ["inventory", SID, "C:/PLMTool"]), \
             patch.object(cli.os, "getpid", return_value=123), \
             patch.object(cli, "collect_windows_processes", return_value=processes), \
             redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["classification"], "DIAGNOSTIC_ONLY")
        self.assertFalse(report["backup_or_migration_authorized"])
        self.assertEqual(report["candidate_processes"][0]["pid"], 42)
        self.assertNotIn("private-password", output.getvalue())

    def test_non_windows_collection_fails_closed(self):
        with patch("plm_assistant.modules.platform.infrastructure.windows_process_inventory.sys.platform",
                   "linux"):
            from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
                collect_windows_processes,
            )
            with self.assertRaises(WindowsProcessInventoryError):
                collect_windows_processes()


if __name__ == "__main__":
    unittest.main()
