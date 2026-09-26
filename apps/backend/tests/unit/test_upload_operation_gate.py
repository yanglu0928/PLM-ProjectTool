from __future__ import annotations

import subprocess
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from plm_assistant.modules.document.infrastructure.upload_operation_gate import (
    LocalUploadOperationGate, UploadGateError,
)


class UploadOperationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gate = LocalUploadOperationGate(self.root)

    def test_same_bucket_excludes_and_release_restores_access(self) -> None:
        first = uuid.UUID("01000000-0000-0000-0000-000000000001")
        collision = uuid.UUID("01ffffff-ffff-ffff-ffff-ffffffffffff")
        second = uuid.UUID("02000000-0000-0000-0000-000000000001")
        other_gate = LocalUploadOperationGate(self.root)
        with self.gate.hold(first):
            with self.assertRaises(UploadGateError):
                with other_gate.hold(collision):
                    self.fail("same bucket must not overlap")
            with other_gate.hold(second):
                pass
        with other_gate.hold(first):
            pass

    def test_cross_process_crash_releases_lock(self) -> None:
        upload_id = uuid.uuid4()
        script = (
            "import sys,uuid; from pathlib import Path; "
            "from plm_assistant.modules.document.infrastructure.upload_operation_gate "
            "import LocalUploadOperationGate; "
            "gate=LocalUploadOperationGate(Path(sys.argv[1])); "
            "with_lock=gate.hold(uuid.UUID(sys.argv[2])); "
            "with_lock.__enter__(); print('LOCKED', flush=True); "
            "sys.stdin.buffer.read()"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root), str(upload_id)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(UploadGateError):
                with self.gate.hold(upload_id):
                    self.fail("other process holds the lock")
        finally:
            child.kill()
            child.communicate(timeout=5)
        with self.gate.hold(upload_id):
            pass

    def test_invalid_id_and_non_regular_lock_file_fail_closed(self) -> None:
        with self.assertRaises(UploadGateError):
            with self.gate.hold(uuid.UUID(int=0)):
                pass
        upload_id = uuid.UUID("aa000000-0000-0000-0000-000000000001")
        path = self.root / ".upload-gates" / "aa.lock"
        path.mkdir()
        with self.assertRaises(UploadGateError):
            with self.gate.hold(upload_id):
                pass

    def test_hardlinked_lock_file_is_rejected(self) -> None:
        upload_id = uuid.UUID("ab000000-0000-0000-0000-000000000001")
        path = self.root / ".upload-gates" / "ab.lock"
        with self.gate.hold(upload_id):
            pass
        try:
            os.link(path, self.root / "linked-lock")
        except OSError:
            self.skipTest("hard-link creation is unavailable for this account")
        with self.assertRaises(UploadGateError):
            with self.gate.hold(upload_id):
                pass

    def test_business_exception_still_releases_lock(self) -> None:
        upload_id = uuid.uuid4()
        with self.assertRaisesRegex(ValueError, "synthetic business failure"):
            with self.gate.hold(upload_id):
                raise ValueError("synthetic business failure")
        with self.gate.hold(upload_id):
            pass


if __name__ == "__main__":
    unittest.main()
