"""Windows Parser CLI requires explicit offline model coordinates and owns cleanup."""

import tempfile
import unittest
import uuid
import signal
import threading
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from plm_assistant.entrypoints import parser_worker_windows
from plm_assistant.entrypoints.parser_worker_signals import (
    parser_worker_signals, run_parser_worker_process,
)
from plm_assistant.modules.parser.application.sweep_expired_cancel import ParserCancelSweepOutcome
from plm_assistant.modules.parser.application.worker_loop import ParserWorkerLoop
from plm_assistant.modules.parser.application.worker_step import ParserWorkerStepOutcome
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class ParserWorkerWindowsTests(unittest.TestCase):
    def test_once_cli_disposes_only_after_quiescent_run(self):
        database = Mock()
        loop = SimpleNamespace(quiescent=lambda: nullcontext())
        with patch.object(parser_worker_windows.sys, "platform", "win32"), \
             patch.object(parser_worker_windows.sys, "argv",
                   ["parser-worker", __file__, "--once"]), \
             patch.object(parser_worker_windows, "load_bootstrap_settings",
                   return_value=object()), \
             patch.object(parser_worker_windows, "create_windows_parser_worker",
                   return_value=(database, loop)), \
             patch.object(parser_worker_windows, "run_parser_worker_process",
                   return_value=SimpleNamespace(reason="LIMIT")) as run:
            self.assertEqual(parser_worker_windows.main(), 0)
            run.assert_called_once_with(loop, max_cycles=1)
            database.dispose.assert_called_once()

    def test_signal_requests_stop_without_running_business_work(self):
        class Step:
            stopped = threading.Event()
            calls = 0

            def request_stop(self):
                self.stopped.set()

            @contextmanager
            def quiescent(self):
                yield

            def step(self):
                self.calls += 1
                return ParserWorkerStepOutcome("IDLE")

        class Sweep:
            calls = 0

            def run_next(self):
                self.calls += 1
                return ParserCancelSweepOutcome("IDLE")

        step, sweep = Step(), Sweep()
        loop = ParserWorkerLoop(step=step, sweep=sweep, poll_seconds=.05)
        original = signal.getsignal(signal.SIGINT)
        with parser_worker_signals(loop):
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(step.stopped.wait(1))
        self.assertIs(signal.getsignal(signal.SIGINT), original)
        self.assertEqual(loop.run(max_cycles=1).reason, "STOPPED")
        self.assertEqual((step.calls, sweep.calls), (0, 0))

    def test_bounded_process_cycle(self):
        class Step:
            @contextmanager
            def quiescent(self):
                yield

            def request_stop(self):
                pass

            def step(self):
                return ParserWorkerStepOutcome("IDLE")

        class Sweep:
            def run_next(self):
                return ParserCancelSweepOutcome("IDLE")

        loop = ParserWorkerLoop(step=Step(), sweep=Sweep(), poll_seconds=.05)
        self.assertEqual(run_parser_worker_process(loop, max_cycles=1).reason, "LIMIT")

    def test_model_configuration_is_absolute_and_complete(self):
        with tempfile.TemporaryDirectory() as root:
            base = dict(data_root=Path(root))
            with self.assertRaises(ValueError):
                BootstrapSettings(**base, parser_ocr_detection_model_dir="relative")
            with self.assertRaises(ValueError):
                BootstrapSettings(**base, parser_ocr_model_fingerprint="invalid")
            with patch.object(parser_worker_windows.sys, "platform", "win32"):
                with self.assertRaises(RuntimeError):
                    parser_worker_windows.create_windows_parser_worker(BootstrapSettings(**base))

    def test_owned_windows_sources_and_model_are_forwarded(self):
        with tempfile.TemporaryDirectory() as root:
            location = Path(root)
            settings = BootstrapSettings(data_root=location,
                parser_ocr_detection_model_dir=location,
                parser_ocr_recognition_model_dir=location,
                parser_ocr_model_fingerprint="a" * 64)
            database = Mock()
            guard = object()
            actor = SimpleNamespace(assert_current=Mock(return_value=uuid.uuid4()))
            loop = object()
            with patch.object(parser_worker_windows.sys, "platform", "win32"), \
                 patch.object(parser_worker_windows, "read_database_url", return_value="owned"), \
                 patch.object(parser_worker_windows, "create_worker_database_runtime", return_value=database), \
                 patch.object(parser_worker_windows, "create_windows_worker_license_services",
                       return_value=SimpleNamespace(guard=guard)), \
                 patch.object(parser_worker_windows, "create_windows_system_actor", return_value=actor), \
                 patch.object(parser_worker_windows, "ProjectAuthorizationService", return_value=object()), \
                 patch.object(parser_worker_windows, "OfflinePaddleOcr") as model, \
                 patch.object(parser_worker_windows, "create_parser_worker", return_value=loop) as compose:
                value = parser_worker_windows.create_windows_parser_worker(settings)
                self.assertEqual(value, (database, loop))
                self.assertEqual(model.call_args.kwargs["expected_model_fingerprint"], "a" * 64)
                self.assertEqual(compose.call_args.kwargs["license_guard"], guard)
                self.assertEqual(compose.call_args.kwargs["system_actor"], actor)
                self.assertEqual(compose.call_args.kwargs["data_root"], location)
                database.dispose.assert_not_called()

    def test_construction_failure_disposes_unstarted_database(self):
        with tempfile.TemporaryDirectory() as root:
            location = Path(root)
            settings = BootstrapSettings(data_root=location,
                parser_ocr_detection_model_dir=location,
                parser_ocr_recognition_model_dir=location,
                parser_ocr_model_fingerprint="a" * 64)
            database = Mock()
            with patch.object(parser_worker_windows.sys, "platform", "win32"), \
                 patch.object(parser_worker_windows, "read_database_url", return_value="owned"), \
                 patch.object(parser_worker_windows, "create_worker_database_runtime", return_value=database), \
                 patch.object(parser_worker_windows, "create_windows_worker_license_services",
                       side_effect=RuntimeError("secret")):
                with self.assertRaisesRegex(RuntimeError, "Windows Parser worker unavailable") as raised:
                    parser_worker_windows.create_windows_parser_worker(settings)
                self.assertNotIn("secret", str(raised.exception))
                database.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
