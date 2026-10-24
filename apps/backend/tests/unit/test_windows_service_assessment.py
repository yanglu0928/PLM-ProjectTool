"""SCM saved-config comparison is strict, redacted and never clearance."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plm_assistant.entrypoints import service_assessment_windows as target
from plm_assistant.entrypoints.service_plan_windows import build_service_plan
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES,
)
from plm_assistant.modules.platform.infrastructure.windows_service_inventory import (
    ServiceObservation, WindowsServiceInventoryError,
)


class FakeReader:
    def __init__(self, observation):
        self.observation = observation

    def read(self, role):
        return self.observation


@unittest.skipUnless(sys.platform == "win32", "Windows SCM only")
class WindowsServiceAssessmentTests(unittest.TestCase):
    account = r".\plmtool"

    def paths(self, directory, *, ai_policy=False):
        root = Path(directory) / "中文 install space"
        root.mkdir()
        python = root / "python.exe"
        python.write_bytes(b"synthetic-exe")
        (root / "det").mkdir()
        (root / "rec").mkdir()
        config = root / "bootstrap.yaml"
        config.write_text(
            f"data_root: {json.dumps(str(root))}\n"
            f"parser_ocr_detection_model_dir: {json.dumps(str(root / 'det'))}\n"
            f"parser_ocr_recognition_model_dir: {json.dumps(str(root / 'rec'))}\n"
            f"parser_ocr_model_fingerprint: {'a' * 64}\n"
            + ("ai_probe_policies:\n"
               "  - reference: endpoint.synthetic.v1\n"
               "    kind: OPENAI_COMPATIBLE\n"
               "    endpoint_url: https://probe.example.test/v1/chat/completions\n"
               "    model_key: synthetic-chat\n"
               "    data_region: cn-beijing\n"
               "    egress_class: EXTERNAL_APPROVAL_REQUIRED\n"
               if ai_policy else ""), encoding="utf-8")
        return python, config

    def observation(self, python, config, *, role="API", **changes):
        command = next(item["binary_path"] for item in
                       build_service_plan(python, config)["service_commands"]
                       if item["role"] == role)
        fields = dict(role=role, service_name=SERVICE_NAMES[role],
                      service_type=16, start_type=3, error_control=1,
                      binary_path=command, start_account=self.account,
                      state=4, reported_pid=3456)
        fields.update(changes)
        return ServiceObservation(**fields)

    def test_exact_configuration_matches_without_clearance_or_secret_output(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            observation = self.observation(python, config)
            report = target.assess_fixed_service(
                "API", python, config, self.account, reader=FakeReader(observation))
            self.assertTrue(report["configuration_matches"])
            self.assertFalse(report["backup_or_migration_authorized"])
            self.assertEqual(report["status"], "CONFIG_MATCH_DIAGNOSTIC_ONLY")
            serialized = json.dumps(report)
            self.assertNotIn(str(python), serialized)
            self.assertNotIn(self.account, serialized)
            self.assertNotIn("3456", serialized)

    def test_ai_assessment_requires_policy_and_remains_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            with self.assertRaises(target.WindowsServiceAssessmentError):
                target.assess_fixed_service("AI_PROVIDER_WORKER", python, config,
                                            self.account, reader=FakeReader(None))
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory, ai_policy=True)
            observation = self.observation(python, config, role="AI_PROVIDER_WORKER")
            report = target.assess_fixed_service(
                "AI_PROVIDER_WORKER", python, config, self.account,
                reader=FakeReader(observation))
            self.assertTrue(report["configuration_matches"])
            self.assertFalse(report["backup_or_migration_authorized"])

    def test_each_saved_field_mismatch_fails_closed(self):
        cases = (
            ("service_type", 32, "SERVICE_TYPE_MISMATCH"),
            ("start_type", 2, "START_TYPE_MISMATCH"),
            ("error_control", 0, "ERROR_CONTROL_MISMATCH"),
            ("binary_path", r"C:\wrong\python.exe", "BINARY_PATH_MISMATCH"),
            ("start_account", r".\other", "ACCOUNT_MISMATCH"),
        )
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            for field, value, code in cases:
                with self.subTest(field=field):
                    observation = self.observation(python, config, **{field: value})
                    report = target.assess_fixed_service(
                        "API", python, config, self.account,
                        reader=FakeReader(observation))
                    self.assertEqual(report["mismatch_codes"], [code])
                    self.assertFalse(report["configuration_matches"])
                    self.assertFalse(report["backup_or_migration_authorized"])

    def test_missing_service_and_invalid_expected_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            report = target.assess_fixed_service(
                "API", python, config, self.account, reader=FakeReader(None))
            self.assertFalse(report["installed"])
            self.assertEqual(report["mismatch_codes"], ["SERVICE_NOT_INSTALLED"])
            for role, account in (("OTHER", self.account), ("API", "LocalSystem"),
                                  ("API", r"NT AUTHORITY\SYSTEM")):
                with self.subTest(role=role, account=account):
                    with self.assertRaises(target.WindowsServiceAssessmentError):
                        target.assess_fixed_service(
                            role, python, config, account, reader=FakeReader(None))
            with self.assertRaises(target.WindowsServiceAssessmentError):
                target.assess_fixed_service(
                    "API", Path("relative/python.exe"), config,
                    self.account, reader=FakeReader(None))

    def test_query_error_is_fixed_and_no_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            with patch.object(target, "read_service_observation",
                              side_effect=WindowsServiceInventoryError()):
                with self.assertRaises(target.WindowsServiceAssessmentError) as error:
                    target.assess_fixed_service("API", python, config, self.account)
            self.assertEqual(str(error.exception),
                             "WINDOWS_SERVICE_ASSESSMENT_UNAVAILABLE")

    def test_native_current_host_remains_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            report = target.assess_fixed_service(
                "API", python, config, self.account)
            self.assertFalse(report["backup_or_migration_authorized"])
            self.assertIn(report["status"], (
                "CONFIG_MATCH_DIAGNOSTIC_ONLY",
                "CONFIG_MISMATCH_DIAGNOSTIC_ONLY"))
            if not report["installed"]:
                self.assertEqual(report["mismatch_codes"],
                                 ["SERVICE_NOT_INSTALLED"])

    def test_cli_hides_account_and_reports_missing_service(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            out, err = io.StringIO(), io.StringIO()
            with patch.object(target.sys, "argv", ["assessment", "--assess", "API",
                                                    str(python), str(config)]), \
                    patch.object(target.sys.stdin, "isatty", return_value=True), \
                    patch.object(target.getpass, "getpass", return_value=self.account), \
                    patch.object(target, "read_service_observation", return_value=None), \
                    redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(target.main(), 1)
            self.assertEqual(json.loads(out.getvalue())["mismatch_codes"],
                             ["SERVICE_NOT_INSTALLED"])
            self.assertNotIn(self.account, out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
