"""Service API reports ready only after a real loopback listener exists."""

from __future__ import annotations

import socket
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from urllib.request import urlopen
from unittest.mock import patch

from fastapi import FastAPI

from plm_assistant.entrypoints import service_windows
from plm_assistant.modules.platform.infrastructure.windows_marker_reconciliation import (
    _read_markers,
)


class WindowsApiServiceTests(unittest.TestCase):
    def test_loopback_listener_ready_http_stop_and_marker_cleanup(self):
        if sys.platform != "win32":
            self.skipTest("native Windows marker only")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = []

            @asynccontextmanager
            async def lifespan(app):
                events.append("startup")
                yield
                events.append("shutdown")

            app = FastAPI(lifespan=lifespan)

            @app.get("/health")
            def health():
                return {"status": "ok"}

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            stop, ready = Event(), Event()
            failures = []

            def runner():
                try:
                    service_windows.run_uvicorn_service(
                        lambda: app, host="127.0.0.1", port=port,
                        data_root=root, log_level="warning",
                        stop_event=stop, ready=ready.set)
                except BaseException as exc:
                    failures.append(type(exc).__name__)

            thread = Thread(target=runner, daemon=False)
            thread.start()
            try:
                self.assertTrue(ready.wait(10))
                self.assertEqual(events, ["startup"])
                self.assertEqual(len(_read_markers(root)), 1)
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
                    self.assertEqual(response.status, 200)
                stop.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
                self.assertEqual(failures, [])
                self.assertEqual(events, ["startup", "shutdown"])
                self.assertEqual(_read_markers(root), ())
            finally:
                stop.set()
                thread.join(10)

    def test_non_loopback_and_bad_app_do_not_report_ready(self):
        if sys.platform != "win32":
            self.skipTest("native Windows marker only")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready = Event()
            with self.assertRaises(service_windows.WindowsApiServiceError):
                service_windows.run_uvicorn_service(lambda: FastAPI(),
                    host="0.0.0.0", port=0, data_root=root,
                    log_level="warning", stop_event=Event(), ready=ready.set)
            self.assertFalse(ready.is_set())
            self.assertEqual(_read_markers(root), ())

            with self.assertRaises(RuntimeError):
                service_windows.run_uvicorn_service(
                    lambda: (_ for _ in ()).throw(RuntimeError("synthetic app failure")),
                    host="127.0.0.1", port=0, data_root=root,
                    log_level="warning", stop_event=Event(), ready=ready.set)
            self.assertFalse(ready.is_set())
            self.assertEqual(len(_read_markers(root)), 1)  # Crash evidence, not clearance.

    def test_unknown_role_is_rejected(self):
        with patch.object(service_windows.sys, "platform", "win32"), \
             patch.object(service_windows.sys, "argv",
                          ["service_windows", "UNKNOWN", "C:/config.yaml"]), \
             patch.object(service_windows, "run_windows_service") as dispatcher:
            self.assertEqual(service_windows.main(), 2)
            dispatcher.assert_not_called()

    def test_api_role_selects_full_platform_write_factory(self):
        settings = SimpleNamespace(bind_host="127.0.0.1", bind_port=9000,
            data_root=Path.cwd(), log_level=SimpleNamespace(value="WARNING"))
        with patch.object(service_windows.sys, "platform", "win32"), \
             patch("plm_assistant.modules.platform.infrastructure.bootstrap_config.load_bootstrap_settings",
                   return_value=settings), \
             patch("plm_assistant.entrypoints.production_login.create_production_platform_write_app",
                   return_value=object()) as factory, \
             patch.object(service_windows, "run_uvicorn_service") as server:
            service_windows.run_api_service(Path(__file__), Event(), lambda: None)
            app_factory = server.call_args.args[0]
            self.assertIsNotNone(app_factory())
            factory.assert_called_once_with(settings)
            self.assertEqual(server.call_args.kwargs["host"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
