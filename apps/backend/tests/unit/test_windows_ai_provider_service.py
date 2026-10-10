"""AI Provider SCM workload never reports clean stop before task quiescence."""

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
        self.stopping = Event()
        self.release = Event()
        self.drained = True

    def request_stop(self):
        self.stopping.set()

    def run(self):
        self.drained = False
        self.running.set()
        self.stopping.wait(3)
        self.release.wait(3)
        self.drained = True
        return SimpleNamespace(reason="STOPPED")

    @contextmanager
    def quiescent(self):
        if not self.drained:
            raise RuntimeError("Provider probe still active")
        yield


class FakeDatabase:
    def __init__(self, loop, *, ready=True, admit=True):
        self.loop = loop
        self.ready = ready
        self.allow_admit = admit
        self.admitted = 0
        self.disposed = False
        self.maintenance_admission = self

    def is_ready(self):
        return self.ready

    @contextmanager
    def admit(self):
        if not self.allow_admit:
            raise RuntimeError("maintenance active")
        self.admitted += 1
        yield

    def dispose(self):
        if not self.loop.drained:
            raise AssertionError("premature disposal")
        self.disposed = True


@unittest.skipUnless(sys.platform == "win32", "native Windows marker only")
class WindowsAIProviderServiceTests(unittest.TestCase):
    def test_stop_waits_for_current_probe_before_marker_and_db_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop = FakeLoop()
            database = FakeDatabase(loop)
            stop, ready = Event(), Event()
            errors = []

            def run():
                try:
                    service_windows.run_ai_provider_loop_service(
                        database, loop, root, stop, ready.set)
                except Exception as error:
                    errors.append(error)

            thread = Thread(target=run, daemon=True)
            thread.start()
            self.assertTrue(ready.wait(3))
            self.assertTrue(loop.running.wait(3))
            self.assertEqual(database.admitted, 1)
            stop.set()
            self.assertTrue(loop.stopping.wait(3))
            self.assertFalse(database.disposed)
            self.assertTrue(any((root / ".plm-runtime-processes").glob("*.json")))
            loop.release.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(database.disposed)
            self.assertFalse(any((root / ".plm-runtime-processes").glob("*.json")))

    def test_unready_maintenance_refusal_never_reports_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            for ready_database, admission in ((False, True), (True, False)):
                with self.subTest(ready_database=ready_database, admission=admission):
                    root = Path(directory)
                    loop = FakeLoop()
                    database = FakeDatabase(loop, ready=ready_database, admit=admission)
                    ready = Event()
                    with self.assertRaises(Exception):
                        service_windows.run_ai_provider_loop_service(
                            database, loop, root, Event(), ready.set)
                    self.assertFalse(ready.is_set())
                    self.assertTrue(database.disposed)

    def test_main_selects_fixed_ai_role(self):
        calls = []
        with patch.object(service_windows.sys, "argv",
                          ["service", "AI_PROVIDER_WORKER", "C:/a.yaml"]), \
             patch.object(service_windows, "run_windows_service",
                          side_effect=lambda role, fn: calls.append(role)):
            self.assertEqual(service_windows.main(), 0)
        self.assertEqual(calls, ["AI_PROVIDER_WORKER"])


if __name__ == "__main__":
    unittest.main()
