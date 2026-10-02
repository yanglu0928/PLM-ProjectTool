"""SCM status must reflect explicit readiness and cooperative completion."""

from __future__ import annotations

import os
import subprocess
import sys
from time import sleep
import unittest

from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    RUNNING, START_PENDING, STOPPED, STOP_PENDING, SERVICE_ACCEPT_STOP,
    SERVICE_NAMES, WindowsServiceDispatcherError, _ServiceLifecycle,
    run_windows_service,
)


class WindowsServiceDispatcherTests(unittest.TestCase):
    def lifecycle(self, fail_state=None):
        reports = []

        def report(state, accepted, error, checkpoint):
            reports.append((state, accepted, error, checkpoint))
            if state == fail_state:
                raise WindowsServiceDispatcherError()

        return _ServiceLifecycle(report), reports

    def test_explicit_ready_stop_and_pending_checkpoint(self):
        service, reports = self.lifecycle()

        def workload(stop, ready):
            self.assertFalse(stop.is_set())
            ready()
            service.request_stop()
            service.request_stop()
            service.stop_pending_tick()
            self.assertTrue(stop.is_set())

        self.assertTrue(service.run(workload))
        self.assertEqual([item[0] for item in reports],
                         [START_PENDING, RUNNING, STOP_PENDING,
                          STOP_PENDING, STOPPED])
        self.assertEqual(reports[1][1], SERVICE_ACCEPT_STOP)
        self.assertEqual([item[3] for item in reports], [1, 0, 1, 2, 0])
        self.assertEqual(reports[-1][2], 0)

    def test_unready_or_unrequested_exit_is_failure(self):
        unready, reports = self.lifecycle()
        self.assertFalse(unready.run(lambda stop, ready: None))
        self.assertEqual([(item[0], item[2]) for item in reports],
                         [(START_PENDING, 0), (STOPPED, 1)])

        unexpected, reports = self.lifecycle()
        self.assertFalse(unexpected.run(lambda stop, ready: ready()))
        self.assertEqual([(item[0], item[2]) for item in reports],
                         [(START_PENDING, 0), (RUNNING, 0), (STOPPED, 1)])

    def test_workload_and_status_failure_cannot_report_clean_stop(self):
        broken, reports = self.lifecycle()

        def raise_after_ready(stop, ready):
            ready()
            raise RuntimeError("synthetic failure")

        self.assertFalse(broken.run(raise_after_ready))
        self.assertEqual(reports[-1][0:3], (STOPPED, 0, 1))

        failed_status, reports = self.lifecycle(fail_state=STOP_PENDING)

        def stop_with_failed_report(stop, ready):
            ready()
            try:
                failed_status.request_stop()
            except WindowsServiceDispatcherError:
                pass

        self.assertFalse(failed_status.run(stop_with_failed_report))
        self.assertEqual(reports[-1][0:3], (STOPPED, 0, 1))

    def test_long_stop_keeps_checkpoint_advancing_until_runner_returns(self):
        reports = []
        service = _ServiceLifecycle(lambda *values: reports.append(values),
                                    pending_tick_seconds=.02)

        def workload(stop, ready):
            ready()
            service.request_stop()
            sleep(.13)  # A synthetic in-flight operation that drains later.

        self.assertTrue(service.run(workload))
        pending = [item[3] for item in reports if item[0] == STOP_PENDING]
        self.assertGreaterEqual(len(pending), 2)
        self.assertEqual(pending, sorted(pending))
        self.assertEqual(reports[-1][0:3], (STOPPED, 0, 0))

    def test_dispatcher_rejects_unknown_role(self):
        with self.assertRaises(WindowsServiceDispatcherError):
            run_windows_service("UNKNOWN", lambda stop, ready: None)
        self.assertEqual(len(set(SERVICE_NAMES.values())), 4)

    @unittest.skipUnless(sys.platform == "win32", "native Windows only")
    def test_native_dispatcher_outside_scm_fails_without_installing(self):
        source = (
            "from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher "
            "import run_windows_service, WindowsServiceDispatcherError\n"
            "try:\n"
            "    run_windows_service('API', lambda stop, ready: None)\n"
            "except WindowsServiceDispatcherError:\n"
            "    print('SCM_REQUIRED')\n"
            "else:\n"
            "    print('UNEXPECTED_DISPATCH')\n"
        )
        result = subprocess.run([sys.executable, "-c", source],
                                capture_output=True, text=True,
                                env=os.environ.copy(), timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "SCM_REQUIRED")


if __name__ == "__main__":
    unittest.main()
