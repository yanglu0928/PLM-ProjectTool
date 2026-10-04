"""Runtime markers are diagnostic and must not silently disappear on failure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.platform.infrastructure.runtime_process_identity import (
    RuntimeProcessIdentity, RuntimeProcessIdentityError, package_code_digest,
    register_runtime_process,
)
from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
    _windows_sid_reader,
)


class RuntimeProcessIdentityTests(unittest.TestCase):
    def identity(self):
        return RuntimeProcessIdentity(
            role="API", pid=12345, registered_at_utc="2026-09-30T00:00:00+00:00",
            package_version="0.1.0.dev0", code_sha256="a" * 64,
            owner_sid="S-1-5-21-100-200-300-400",
            executable_path="C:\\PLMTool\\runtime\\python.exe", nonce="f" * 32,
        )

    def test_package_digest_changes_with_source_not_pycache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core.py").write_text("initial", encoding="utf-8")
            first = package_code_digest(root)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "core.pyc").write_bytes(b"ignored")
            self.assertEqual(package_code_digest(root), first)
            (root / "core.py").write_text("changed", encoding="utf-8")
            self.assertNotEqual(package_code_digest(root), first)

    def test_normal_exit_removes_only_owned_marker(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity.sys.platform", "win32"), \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity._identity",
                   return_value=self.identity()):
            root = Path(directory)
            with register_runtime_process("API", root) as identity:
                files = list((root / ".plm-runtime-processes").glob("*.json"))
                self.assertEqual(len(files), 1)
                record = json.loads(files[0].read_text(encoding="utf-8"))
                self.assertEqual((record["role"], record["pid"], record["owner_sid"]),
                                 ("API", identity.pid, identity.owner_sid))
                self.assertEqual(record["code_sha256"], "a" * 64)
            self.assertFalse(files[0].exists())

    def test_abnormal_exit_leaves_marker_for_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity.sys.platform", "win32"), \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity._identity",
                   return_value=self.identity()):
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "synthetic application failure"):
                with register_runtime_process("API", root):
                    raise RuntimeError("synthetic application failure")
            self.assertEqual(len(list((root / ".plm-runtime-processes").glob("*.json"))), 1)

    def test_tampered_marker_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity.sys.platform", "win32"), \
             patch("plm_assistant.modules.platform.infrastructure.runtime_process_identity._identity",
                   return_value=self.identity()):
            root = Path(directory)
            with self.assertRaises(RuntimeProcessIdentityError):
                with register_runtime_process("API", root):
                    marker = next((root / ".plm-runtime-processes").glob("*.json"))
                    marker.write_text("tampered", encoding="utf-8")
            self.assertEqual(marker.read_text(encoding="utf-8"), "tampered")

    def test_invalid_role_fails_before_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeProcessIdentityError):
                with register_runtime_process("UNKNOWN", root):
                    pass
            self.assertFalse((root / ".plm-runtime-processes").exists())

    @unittest.skipUnless(sys.platform == "win32", "native Windows process only")
    def test_native_child_pid_sid_version_digest_and_crash_marker(self):
        child_source = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "from plm_assistant.modules.platform.infrastructure.runtime_process_identity "
            "import register_runtime_process\n"
            "with register_runtime_process('API', Path(sys.argv[1])):\n"
            "    print(f'READY {os.getpid()}', flush=True)\n"
            "    if sys.stdin.readline().strip() == 'crash':\n"
            "        os._exit(7)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker_dir = root / ".plm-runtime-processes"
            for crash in (False, True):
                child = subprocess.Popen(
                    [sys.executable, "-c", child_source, str(root)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, env=os.environ.copy(),
                )
                try:
                    ready = child.stdout.readline().strip().split()
                    self.assertEqual(ready[0], "READY")
                    actual_pid = int(ready[1])
                    markers = list(marker_dir.glob("*.json"))
                    self.assertEqual(len(markers), 1)
                    record = json.loads(markers[0].read_text(encoding="utf-8"))
                    self.assertEqual(record["pid"], actual_pid)
                    self.assertEqual(record["owner_sid"], _windows_sid_reader()(actual_pid))
                    self.assertEqual(record["package_version"], "0.1.0.dev0")
                    self.assertEqual(record["code_sha256"], package_code_digest(
                        Path(__file__).resolve().parents[2] / "src" / "plm_assistant"))
                    self.assertEqual(Path(record["executable_path"]),
                                     Path(sys.executable).resolve())
                    if crash:
                        child.stdin.write("crash\n")
                    else:
                        child.stdin.write("\n")
                    child.stdin.flush()
                    child.wait(timeout=15)
                    self.assertEqual(child.returncode != 0, crash)
                    self.assertEqual(markers[0].exists(), crash)
                    if crash:
                        markers[0].unlink()  # Synthetic temp marker only.
                finally:
                    if child.poll() is None:
                        child.terminate()
                        child.wait(timeout=15)
                    child.stdin.close()
                    child.stdout.close()
                    child.stderr.close()


if __name__ == "__main__":
    unittest.main()
