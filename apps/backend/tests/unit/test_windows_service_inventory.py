"""SCM observation is diagnostic only, including on a real Windows host."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from plm_assistant.entrypoints import service_inventory_windows as cli
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    RUNNING, SERVICE_NAMES, STOPPED, STOP_PENDING,
)
from plm_assistant.modules.platform.infrastructure import windows_service_inventory as inv


class FakeReader:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def read(self, role):
        self.calls.append(role)
        return self.value


@unittest.skipUnless(sys.platform == "win32", "Windows SCM only")
class WindowsServiceInventoryTests(unittest.TestCase):
    def observation(self, state=RUNNING, pid=1234):
        return inv.ServiceObservation(
            "API", SERVICE_NAMES["API"], 16, 3, 1,
            r"C:\private\python.exe --secret=synthetic-secret",
            r"DOMAIN\sensitive-user", state, pid)

    def test_running_pid_only_in_running_state(self):
        self.assertEqual(self.observation().running_pid, 1234)
        self.assertIsNone(self.observation(STOP_PENDING).running_pid)
        self.assertIsNone(self.observation(STOPPED).running_pid)
        self.assertIsNone(self.observation(RUNNING, 0).running_pid)
        self.assertNotIn("synthetic-secret", repr(self.observation()))
        self.assertNotIn("sensitive-user", repr(self.observation()))

    def test_fixed_role_reader_and_mismatch_fail_closed(self):
        fake = FakeReader(self.observation())
        self.assertIs(inv.read_service_observation("API", reader=fake), fake.value)
        self.assertEqual(fake.calls, ["API"])
        with self.assertRaises(inv.WindowsServiceInventoryError):
            inv.read_service_observation("OTHER", reader=fake)
        with self.assertRaises(inv.WindowsServiceInventoryError):
            inv.read_service_observation("AUDIT_WORKER", reader=fake)
        with self.assertRaises(inv.WindowsServiceInventoryError):
            inv.ServiceObservation("API", "wrong", 16, 3, 1, "", "")

    def test_redacted_cli_report_never_grants_clearance(self):
        with patch.object(cli, "read_service_observation",
                          return_value=self.observation()):
            report = cli.build_inventory(("API",))
        serialized = json.dumps(report)
        self.assertEqual(report["classification"], "DIAGNOSTIC_ONLY")
        self.assertFalse(report["backup_or_migration_authorized"])
        self.assertEqual(report["services"][0]["running_pid"], 1234)
        self.assertNotIn("synthetic-secret", serialized)
        self.assertNotIn("sensitive-user", serialized)
        self.assertNotIn("binary_path", serialized)
        with patch.object(cli, "read_service_observation", return_value=None):
            absent = cli.build_inventory(("API",))
        self.assertEqual(absent["services"][0]["installed"], False)
        self.assertFalse(absent["backup_or_migration_authorized"])

    def test_cli_invalid_role_and_query_failure_do_not_emit_partial_report(self):
        with patch.object(cli.sys, "argv", ["inventory", "OTHER"]):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(cli.main(), 2)
            self.assertEqual(output.getvalue(), "")
        with patch.object(cli.sys, "argv", ["inventory", "ALL"]), \
                patch.object(cli, "read_service_observation",
                             side_effect=inv.WindowsServiceInventoryError()):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(cli.main(), 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("no clearance", errors.getvalue())

    def test_native_fixed_services_read_only(self):
        for role in SERVICE_NAMES:
            value = inv.read_service_observation(role)
            if value is not None:
                self.assertEqual(value.role, role)
                self.assertEqual(value.service_name, SERVICE_NAMES[role])
                if value.state != RUNNING:
                    self.assertIsNone(value.running_pid)

    def test_native_installed_system_service_config_and_status_read_only(self):
        # EventLog is a Windows-owned fixture; never alter or expose its config.
        values = inv._NativeServiceQuery()._read_name("EventLog")
        if values is None:
            self.skipTest("EventLog not installed on this Windows host")
        service_type, start_type, error_control, path, account, state, pid = values
        self.assertGreater(service_type, 0)
        self.assertGreaterEqual(start_type, 0)
        self.assertGreaterEqual(error_control, 0)
        self.assertTrue(path)
        self.assertTrue(account)
        self.assertGreater(state, 0)
        if state == RUNNING:
            self.assertGreater(pid, 0)


if __name__ == "__main__":
    unittest.main()
