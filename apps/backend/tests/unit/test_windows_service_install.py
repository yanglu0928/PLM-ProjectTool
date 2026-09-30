"""Fixed-role SCM registration never overwrites or starts a service."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from plm_assistant.entrypoints import service_install_windows as installer
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES,
)


class FakeSCM:
    def __init__(self, *, manager=11, service=22):
        self.manager = manager
        self.service = service
        self.calls = []
        self.password_buffer = None

    def open_manager(self):
        self.calls.append("open")
        return self.manager

    def create_service(self, manager, *, name, binary_path, account,
                       password_buffer):
        self.calls.append((manager, name, binary_path, account))
        self.password_buffer = password_buffer
        return self.service

    def close_handle(self, handle):
        self.calls.append(("close", handle))


@unittest.skipUnless(sys.platform == "win32", "Windows SCM only")
class WindowsServiceInstallTests(unittest.TestCase):
    def paths(self, directory):
        root = Path(directory) / "中文 package space"
        root.mkdir()
        python = root / "python.exe"
        python.write_bytes(b"synthetic-exe")
        (root / "det").mkdir()
        (root / "rec").mkdir()
        bootstrap = root / "bootstrap.yaml"
        bootstrap.write_text(
            f"data_root: {json.dumps(str(root))}\n"
            f"parser_ocr_detection_model_dir: {json.dumps(str(root / 'det'))}\n"
            f"parser_ocr_recognition_model_dir: {json.dumps(str(root / 'rec'))}\n"
            f"parser_ocr_model_fingerprint: {'a' * 64}\n", encoding="utf-8")
        return python, bootstrap

    def test_single_role_manual_service_and_password_scrub(self):
        with tempfile.TemporaryDirectory() as directory:
            python, bootstrap = self.paths(directory)
            fake = FakeSCM()
            with patch.object(installer.sys, "executable", str(python)):
                installer.install_fixed_service(
                    "AUDIT_WORKER", python, bootstrap, ".\\plmtool",
                    "synthetic-pass", scm=fake)
            self.assertEqual(fake.calls[0], "open")
            manager, name, command, account = fake.calls[1]
            self.assertEqual((manager, name, account),
                             (11, SERVICE_NAMES["AUDIT_WORKER"], ".\\plmtool"))
            self.assertIn("service_windows AUDIT_WORKER", command)
            self.assertNotIn("synthetic-pass", command)
            self.assertEqual(fake.calls[-2:], [("close", 22), ("close", 11)])
            self.assertEqual(fake.password_buffer.value, "")

    def test_existing_name_or_access_denied_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            python, bootstrap = self.paths(directory)
            duplicate = FakeSCM(service=None)
            with patch.object(installer.sys, "executable", str(python)):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.install_fixed_service(
                        "API", python, bootstrap, ".\\plmtool", "not-logged",
                        scm=duplicate)
            self.assertEqual(duplicate.calls[-1], ("close", 11))
            self.assertEqual(duplicate.password_buffer.value, "")
            denied = FakeSCM(manager=None)
            with patch.object(installer.sys, "executable", str(python)):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.install_fixed_service(
                        "API", python, bootstrap, ".\\plmtool", "not-logged",
                        scm=denied)
            self.assertEqual(denied.calls, ["open"])

    def test_rejects_builtin_account_role_and_password_in_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            python, bootstrap = self.paths(directory)
            fake = FakeSCM()
            for role, account, password in (
                    ("UNKNOWN", ".\\plmtool", "x"),
                    ("API", "NT AUTHORITY\\SYSTEM", "x"),
                    ("API", ".\\plmtool", ""),
                    ("API", ".\\plmtool", "x\x00y")):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.install_fixed_service(
                        role, python, bootstrap, account, password, scm=fake)
            self.assertEqual(fake.calls, [])
            with patch.object(installer.sys, "argv", ["install", "--install", "API",
                 str(python), str(bootstrap), ".\\plmtool", "password"]), \
                 patch.object(installer.sys, "stdin",
                              SimpleNamespace(isatty=lambda: True)), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(installer.main(), 2)

    def test_rejects_other_interpreter_and_bad_package_before_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            python, bootstrap = self.paths(directory)
            fake = FakeSCM()
            with self.assertRaises(installer.WindowsServiceInstallError):
                installer.install_fixed_service(
                    "API", python, bootstrap, ".\\plmtool", "synthetic",
                    scm=fake)
            self.assertEqual(fake.calls, [])
            with patch.object(installer.sys, "executable", str(python)), \
                 patch.object(installer.metadata, "version", return_value="wrong"):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.install_fixed_service(
                        "API", python, bootstrap, ".\\plmtool", "synthetic",
                        scm=fake)
            with patch.object(installer.sys, "executable", str(python)), \
                 patch.object(installer.struct, "calcsize", return_value=4):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.verify_installer_runtime(python)
            with patch.object(installer.sys, "executable", str(python)), \
                 patch.object(installer.metadata, "version",
                              side_effect=installer.metadata.PackageNotFoundError):
                with self.assertRaises(installer.WindowsServiceInstallError):
                    installer.verify_installer_runtime(python)
            self.assertEqual(fake.calls, [])
            with patch.object(installer.sys, "argv", ["install", "--install", "API",
                 str(python), str(bootstrap), ".\\plmtool"]), \
                 patch.object(installer.sys, "stdin",
                              SimpleNamespace(isatty=lambda: True)), \
                 patch.object(installer.getpass, "getpass") as prompt, \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(installer.main(), 1)
            prompt.assert_not_called()

    def test_current_interpreter_package_version_is_valid(self):
        installer.verify_installer_runtime(Path(sys.executable))

    def test_native_api_binding_is_available_without_creating_service(self):
        native = installer._NativeServiceControl()
        self.assertTrue(callable(native.open_manager))
        self.assertTrue(callable(native.create_service))


if __name__ == "__main__":
    unittest.main()
