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
    def paths(self, directory: str):
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
            f"parser_ocr_model_fingerprint: {'a' * 64}\n",
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
                              for item in entries], list(SERVICE_NAMES.items()))
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


if __name__ == "__main__":
    unittest.main()
