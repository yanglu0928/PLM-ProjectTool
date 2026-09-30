"""Parser SCM runner owns the complete stop and quiescence window."""

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


class FakeParserLoop:
    def __init__(self):
        self.running = Event()
        self.stopping = Event()
        self.release = Event()
        self.heartbeat_stopped = Event()
        self.heartbeat_stopped.set()
        self.drained = False

    def request_stop(self):
        self.stopping.set()

    def run(self):
        self.running.set()
        self.stopping.wait(3)
        self.release.wait(3)
        self.drained = True
        return SimpleNamespace(reason="STOPPED")

    @contextmanager
    def quiescent(self):
        if not self.drained or not self.heartbeat_stopped.is_set():
            raise RuntimeError("parser or heartbeat still live")
        yield


class FakeDatabase:
    def __init__(self, loop):
        self.loop = loop
        self.disposed = False

    def dispose(self):
        if not self.loop.drained or not self.loop.heartbeat_stopped.is_set():
            raise AssertionError("premature dispose")
        self.disposed = True


@unittest.skipUnless(sys.platform == "win32", "native Windows marker only")
class WindowsParserServiceTests(unittest.TestCase):
    def test_active_work_and_heartbeat_both_drain_before_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop = FakeParserLoop()
            loop.heartbeat_stopped.clear()
            database = FakeDatabase(loop)
            stop, ready = Event(), Event()
            errors = []

            def run():
                try:
                    service_windows.run_parser_loop_service(
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
            loop.release.set()
            self.assertTrue(any((root / ".plm-runtime-processes").glob("*.json")))
            self.assertTrue(worker.is_alive())
            loop.heartbeat_stopped.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(database.disposed)
            self.assertFalse(any((root / ".plm-runtime-processes").glob("*.json")))

    def test_unready_failure_disposes_but_retains_crash_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop = FakeParserLoop()
            loop.drained = True
            database = FakeDatabase(loop)
            with self.assertRaises(RuntimeError):
                service_windows.run_parser_loop_service(
                    database, loop, root, Event(),
                    lambda: (_ for _ in ()).throw(RuntimeError("not ready")))
            self.assertTrue(database.disposed)
            self.assertTrue(any((root / ".plm-runtime-processes").glob("*.json")))

    def test_main_selects_parser_role(self):
        calls = []
        with patch.object(service_windows.sys, "argv", ["service", "PARSER_WORKER", "C:/a.yaml"]), \
             patch.object(service_windows, "run_windows_service",
                          side_effect=lambda role, fn: calls.append(role)):
            self.assertEqual(service_windows.main(), 0)
        self.assertEqual(calls, ["PARSER_WORKER"])


if __name__ == "__main__":
    unittest.main()
