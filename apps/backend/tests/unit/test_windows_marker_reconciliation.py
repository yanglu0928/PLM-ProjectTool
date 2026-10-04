"""Runtime marker cross-check must stay conservative and read-only."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from plm_assistant.entrypoints import process_identity_inventory_windows as cli
from plm_assistant.modules.platform.infrastructure.windows_marker_reconciliation import (
    WindowsMarkerReconciliationError, _read_markers, reconcile_runtime_markers,
)
from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
    ProcessObservation, assess_processes, collect_windows_processes,
)


SID = "S-1-5-21-100-200-300-400"
EXE = "C:\\PLMTool\\runtime\\python.exe"
CMD = "python -m plm_assistant.entrypoints.serve_windows config.toml"


def record(pid=42, role="API"):
    return {"schema_version": 1, "role": role, "pid": pid,
            "registered_at_utc": "2026-09-30T00:00:00+00:00",
            "package_version": "0.1.0.dev0", "code_sha256": "a" * 64,
            "owner_sid": SID, "executable_path": EXE, "nonce": "f" * 32}


def process(pid=42, sid=SID, command=CMD):
    return ProcessObservation(pid, "python.exe", sid, EXE, command,
                              "2026-09-29T23:59:00+00:00")


class MarkerReconciliationTests(unittest.TestCase):
    def assess(self, observations):
        return assess_processes(observations, deployment_sid=SID,
                                runtime_root=PureWindowsPath("C:/PLMTool"),
                                observer_pid=999999)

    def check(self, records, observations):
        with patch("plm_assistant.modules.platform.infrastructure.windows_marker_reconciliation._read_markers",
                   return_value=records), \
             patch("plm_assistant.modules.platform.infrastructure.windows_marker_reconciliation.package_code_digest",
                   return_value="a" * 64):
            return reconcile_runtime_markers(Path("C:/synthetic"), observations,
                                             self.assess(observations))

    def test_live_match_and_unmarked_candidate_never_grant_clearance(self):
        result = self.check((record(),), (process(), process(43)))
        self.assertEqual([(item.pid, item.status) for item in result.findings],
                         [(42, "OBSERVED_MATCH")])
        self.assertEqual(result.unmatched_candidates, (43,))
        self.assertEqual(result.classification, "DIAGNOSTIC_ONLY")

    def test_stale_reused_pid_unreadable_and_conflict(self):
        self.assertEqual(self.check((record(),), ()).findings[0].status,
                         "PID_NOT_OBSERVED")
        self.assertEqual(self.check((record(),), (process(sid="S-1-5-18"),))
                         .findings[0].status, "IDENTITY_MISMATCH")
        reused = ProcessObservation(42, "python.exe", SID, EXE, CMD,
                                    "2026-09-30T00:01:00+00:00")
        self.assertEqual(self.check((record(),), (reused,)).findings[0].status,
                         "IDENTITY_MISMATCH")
        self.assertEqual(self.check((record(),), (process(command=None),))
                         .findings[0].status, "OS_IDENTITY_UNREADABLE")
        self.assertEqual(self.check((record(), record(role="AUDIT_WORKER")),
                                    (process(),)).findings[0].status,
                         "CONFLICTING_MARKERS")

    def test_version_digest_and_role_mismatch(self):
        old = record()
        old["package_version"] = "0.0.1"
        self.assertEqual(self.check((old,), (process(),)).findings[0].status,
                         "IDENTITY_MISMATCH")
        bad_digest = record()
        bad_digest["code_sha256"] = "b" * 64
        self.assertEqual(self.check((bad_digest,), (process(),)).findings[0].status,
                         "IDENTITY_MISMATCH")
        self.assertEqual(self.check((record(),),
                                    (process(command="python -m other"),))
                         .findings[0].status, "IDENTITY_MISMATCH")
        self.assertEqual(self.check((record(),),
            (process(command="python -m plm_assistant.entrypoints.service_windows API C:/config.yaml"),))
            .findings[0].status, "OBSERVED_MATCH")
        self.assertEqual(self.check((record(),),
            (process(command="python -m plm_assistant.entrypoints.service_windows AUDIT_WORKER C:/config.yaml"),))
            .findings[0].status, "IDENTITY_MISMATCH")  # API marker cannot match Audit role.
        self.assertEqual(self.check((record(role="AUDIT_WORKER"),),
            (process(command="python -m plm_assistant.entrypoints.service_windows AUDIT_WORKER C:/config.yaml"),))
            .findings[0].status, "OBSERVED_MATCH")
        self.assertEqual(self.check((record(role="PARSER_WORKER"),),
            (process(command="python -m plm_assistant.entrypoints.service_windows PARSER_WORKER C:/config.yaml"),))
            .findings[0].status, "OBSERVED_MATCH")
        self.assertEqual(self.check((record(role="AI_PROVIDER_WORKER"),),
            (process(command="python -m plm_assistant.entrypoints.service_windows AI_PROVIDER_WORKER C:/config.yaml"),))
            .findings[0].status, "OBSERVED_MATCH")

    def test_native_bounded_marker_reader_rejects_invalid_and_never_deletes(self):
        if sys.platform != "win32":
            self.skipTest("native Windows reader only")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(_read_markers(root), ())
            marker_dir = root / ".plm-runtime-processes"
            marker_dir.mkdir()
            marker = marker_dir / f"api-42-{'f' * 32}.json"
            marker.write_text(json.dumps(record()), encoding="utf-8")
            self.assertEqual(_read_markers(root)[0]["pid"], 42)
            marker.write_bytes(b"x" * 2049)
            with self.assertRaises(WindowsMarkerReconciliationError):
                _read_markers(root)
            self.assertTrue(marker.exists())
            marker.write_text(json.dumps(record())[:-1] + ',"pid":42}', encoding="utf-8")
            with self.assertRaises(WindowsMarkerReconciliationError):
                _read_markers(root)
            self.assertTrue(marker.exists())
            marker.unlink()
            marker_dir.rmdir()
            marker_dir.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(WindowsMarkerReconciliationError):
                _read_markers(root)

    def test_cli_output_is_redacted_and_always_no_clearance(self):
        output = io.StringIO()
        observations = (process(),)
        with patch.object(cli.sys, "platform", "win32"), \
             patch.object(cli.sys, "argv", ["inventory", SID, "C:/PLMTool", "C:/data"]), \
             patch.object(cli.os, "getpid", return_value=999999), \
             patch.object(cli, "collect_windows_processes", return_value=observations), \
             patch.object(cli, "reconcile_runtime_markers",
                          return_value=self.check((record(),), observations)), \
             redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
        report = json.loads(output.getvalue())
        self.assertFalse(report["backup_or_migration_authorized"])
        self.assertEqual(report["marker_findings"][0]["status"], "OBSERVED_MATCH")
        self.assertNotIn(EXE, output.getvalue())
        self.assertNotIn(CMD, output.getvalue())

    @unittest.skipUnless(sys.platform == "win32", "native Windows process only")
    def test_native_child_marker_without_known_entrypoint_is_rejected(self):
        child_source = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "from plm_assistant.modules.platform.infrastructure.runtime_process_identity "
            "import register_runtime_process\n"
            "with register_runtime_process('API', Path(sys.argv[1])):\n"
            "    print(f'READY {os.getpid()}', flush=True)\n"
            "    sys.stdin.readline()\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = subprocess.Popen([sys.executable, "-c", child_source, str(root)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=os.environ.copy())
            try:
                ready = child.stdout.readline().strip().split()
                self.assertEqual(ready[0], "READY")
                actual_pid = int(ready[1])
                record_on_disk = _read_markers(root)[0]
                observations = collect_windows_processes()
                candidates = assess_processes(observations,
                    deployment_sid=record_on_disk["owner_sid"],
                    runtime_root=PureWindowsPath("C:/PLMTool"),
                    observer_pid=os.getpid())
                result = reconcile_runtime_markers(root, observations, candidates)
                self.assertEqual(result.findings[0].pid, actual_pid)
                self.assertEqual(result.findings[0].status, "IDENTITY_MISMATCH")
                self.assertEqual(result.classification, "DIAGNOSTIC_ONLY")
                child.stdin.write("\n")
                child.stdin.flush()
                self.assertEqual(child.wait(timeout=15), 0)
                self.assertEqual(_read_markers(root), ())
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=15)
                child.stdin.close()
                child.stdout.close()
                child.stderr.close()


if __name__ == "__main__":
    unittest.main()
