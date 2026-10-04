"""SCM planning is fixed-role, read-only and explicitly not installation."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plm_assistant.entrypoints import service_plan_windows as plan
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES,
)


@unittest.skipUnless(sys.platform == "win32", "Windows-only SCM plan")
class WindowsServicePlanTests(unittest.TestCase):
    def paths(self, directory: str, *, ai_policy: bool = False):
        root = Path(directory) / "中文 install space"
        root.mkdir()
        python = root / "python.exe"
        python.write_bytes(b"synthetic-not-executable")
        detection = root / "det"
        recognition = root / "rec"
        detection.mkdir()
        recognition.mkdir()
        config = root / "bootstrap.yaml"
        config.write_text(
            f"data_root: {json.dumps(str(root))}\n"
            f"parser_ocr_detection_model_dir: {json.dumps(str(detection))}\n"
            f"parser_ocr_recognition_model_dir: {json.dumps(str(recognition))}\n"
            f"parser_ocr_model_fingerprint: {'a' * 64}\n"
            + ("ai_probe_policies:\n"
               "  - reference: endpoint.synthetic.v1\n"
               "    kind: OPENAI_COMPATIBLE\n"
               "    endpoint_url: https://probe.example.test/v1/chat/completions\n"
               "    model_key: synthetic-chat\n"
               "    data_region: cn-beijing\n"
               "    egress_class: EXTERNAL_APPROVAL_REQUIRED\n"
               if ai_policy else ""),
                          encoding="utf-8")
        return python, config

    def test_three_fixed_commands_and_no_clearance(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            result = plan.build_service_plan(python, config)
            self.assertEqual(result["status"], "PLAN_ONLY")
            self.assertFalse(result["scm_installed"])
            self.assertFalse(result["runtime_and_account_verified"])
            self.assertFalse(result["backup_or_migration_authorized"])
            entries = result["service_commands"]
            self.assertEqual([(item["role"], item["service_name"])
                              for item in entries],
                             [(role, name) for role, name in SERVICE_NAMES.items()
                              if role != "AI_PROVIDER_WORKER"])
            for item in entries:
                self.assertIn('"' + str(python) + '"', item["binary_path"])
                self.assertIn('"' + str(config) + '"', item["binary_path"])
                self.assertIn(" -m plm_assistant.entrypoints.service_windows ",
                              item["binary_path"])
                self.assertNotIn("password", item["binary_path"].lower())
                self.assertNotIn("key=", item["binary_path"].lower())

    def test_invalid_paths_and_secret_field_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(Path("relative/python.exe"), config)
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(python.with_name("pythonw.exe"), config)
            config.write_text(f"data_root: {json.dumps(str(python.parent))}\n",
                              encoding="utf-8")
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(python, config)
            config.write_text("data_root: C:/safe\npassword: SHOULD_NOT_ECHO\n",
                              encoding="utf-8")
            with self.assertRaises(plan.WindowsServicePlanError) as error:
                plan.build_service_plan(python, config)
            self.assertNotIn("SHOULD_NOT_ECHO", str(error.exception))

    def test_cli_is_plan_only_and_does_not_touch_scm(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            output = io.StringIO()
            with patch.object(plan.sys, "argv", ["plan", str(python), str(config)]), \
                 redirect_stdout(output):
                self.assertEqual(plan.main(), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "PLAN_ONLY")
            self.assertEqual(len(result["service_commands"]), 3)

    def test_valid_policy_adds_only_fixed_ai_command(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory, ai_policy=True)
            result = plan.build_service_plan(python, config)
            self.assertEqual([(item["role"], item["service_name"])
                              for item in result["service_commands"]],
                             list(SERVICE_NAMES.items()))
            self.assertFalse(result["backup_or_migration_authorized"])

    def test_invalid_ai_policy_never_emits_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory, ai_policy=True)
            config.write_text(config.read_text(encoding="utf-8").replace(
                "https://probe.example.test/v1/chat/completions",
                "http://127.0.0.1/v1/chat/completions"), encoding="utf-8")
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(python, config)

    def test_complete_business_policy_adds_ai_and_incomplete_pair_fails(self):
        task_yaml = (
            "ai_task_policies:\n"
            "  - reference: gap-analysis.v1\n"
            "    policy_version: 1\n"
            "    task_type: GAP_ANALYSIS\n"
            "    prompt_template_id: 11111111-1111-4111-8111-111111111111\n"
            "    purpose_ref: project-gap-analysis.v1\n"
            "    output_schema_ref: gap-output.v1\n"
            "    context_policy_ref: no-retrieval.v1\n"
            "    parameter_fields: []\n"
        )
        execution_yaml = (
            "ai_execution_policies:\n"
            "  - reference: endpoint.business.v1\n"
            "    kind: OPENAI_COMPATIBLE\n"
            "    endpoint_url: https://business.example.test/v1/chat/completions\n"
            "    data_region: cn-beijing\n"
            "    egress_class: EXTERNAL_APPROVAL_REQUIRED\n"
            "    allowed_model_keys: [business-chat]\n"
            "    max_response_bytes: 1048576\n"
            "    connect_timeout_seconds: 5\n"
            "    read_timeout_seconds: 30\n"
            "    total_timeout_seconds: 40\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            python, config = self.paths(directory)
            base = config.read_text(encoding="utf-8")
            config.write_text(base + task_yaml, encoding="utf-8")
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(python, config)
            config.write_text(base + execution_yaml, encoding="utf-8")
            with self.assertRaises(plan.WindowsServicePlanError):
                plan.build_service_plan(python, config)
            config.write_text(base + task_yaml + execution_yaml, encoding="utf-8")
            result = plan.build_service_plan(python, config)
            self.assertEqual(
                [item["role"] for item in result["service_commands"]],
                list(SERVICE_NAMES),
            )


if __name__ == "__main__":
    unittest.main()
