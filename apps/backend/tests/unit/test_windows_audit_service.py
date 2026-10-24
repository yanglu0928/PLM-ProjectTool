"""Audit SCM runner must drain before database disposal and marker removal."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import patch

from plm_assistant.entrypoints import service_windows


class FakeLoop:
    def __init__(self):
        self.running = Event()
        self.release = Event()
        self.stopping = Event()
        self.drained = False
        self.heartbeat_stopped = Event()
        self.heartbeat_stopped.set()

    def request_stop(self):
        self.stopping.set()

    def run(self, *, stop_requested):
        self.running.set()
        self.stopping.wait(3)
        self.release.wait(3)
        self.drained = True
        return SimpleNamespace(reason="STOPPED")

    @contextmanager
    def quiescent(self):
        if not self.drained or not self.heartbeat_stopped.is_set():
            raise RuntimeError("still running")
        yield


class FakeDatabase:
    def __init__(self, loop):
        self.loop = loop
        self.disposed = False

    def dispose(self):
        if not self.loop.drained:
            raise AssertionError("premature database dispose")
        self.disposed = True


@unittest.skipUnless(sys.platform == "win32", "native Windows marker only")
class WindowsAuditServiceTests(unittest.TestCase):
    def test_scm_stop_waits_for_work_and_removes_marker_after_dispose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = Event()
            ready = Event()
            loop = FakeLoop()
            database = FakeDatabase(loop)
            errors = []

            def run():
                try:
                    service_windows.run_audit_loop_service(
                        database, loop, root, stop, ready.set)
                except Exception as error:
                    errors.append(error)

            worker = Thread(target=run, daemon=True)
            worker.start()
            self.assertTrue(ready.wait(3))
            self.assertTrue(loop.running.wait(3))
            stop.set()
            self.assertTrue(loop.stopping.wait(3))
            self.assertFalse(database.disposed)
            self.assertTrue(worker.is_alive())
            loop.release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(database.disposed)
            self.assertFalse(any((root / ".plm-runtime-processes").glob("*.json")))

    def test_finished_loop_waits_for_heartbeat_quiescence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = Event()
            loop = FakeLoop()
            loop.heartbeat_stopped.clear()
            database = FakeDatabase(loop)
            errors = []

            def run():
                try:
                    service_windows.run_audit_loop_service(
                        database, loop, root, stop, lambda: None)
                except Exception as error:
                    errors.append(error)

            worker = Thread(target=run, daemon=True)
            worker.start()
            self.assertTrue(loop.running.wait(3))
            stop.set()
            loop.release.set()
            self.assertTrue(loop.stopping.wait(3))
            self.assertTrue(any((root / ".plm-runtime-processes").glob("*.json")))
            self.assertFalse(database.disposed)
            self.assertTrue(worker.is_alive())
            loop.heartbeat_stopped.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(database.disposed)

    def test_unready_failure_still_disposes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = Event()
            loop = FakeLoop()
            loop.drained = True
            database = FakeDatabase(loop)
            with self.assertRaises(RuntimeError):
                service_windows.run_audit_loop_service(
                    database, loop, root, stop,
                    lambda: (_ for _ in ()).throw(RuntimeError("not ready")))
            self.assertTrue(database.disposed)
            # Failed startup retains crash evidence for conservative reconciliation.
            self.assertTrue(any((root / ".plm-runtime-processes").glob("*.json")))

    def test_main_selects_only_fixed_service_role(self):
        with patch.object(service_windows.sys, "argv", ["service", "UNKNOWN", "C:/a.yaml"]):
            self.assertEqual(service_windows.main(), 2)
        calls = []
        with patch.object(service_windows.sys, "argv", ["service", "AUDIT_WORKER", "C:/a.yaml"]), \
             patch.object(service_windows, "run_windows_service",
                          side_effect=lambda role, fn: calls.append(role)):
            self.assertEqual(service_windows.main(), 0)
        self.assertEqual(calls, ["AUDIT_WORKER"])


if __name__ == "__main__":
    unittest.main()
