from __future__ import annotations

import time
import unittest
from unittest.mock import Mock

from resource_observer import ResourceObserver, cpu_percent, summarize_samples


class ResourceObserverTests(unittest.TestCase):
    def test_cpu_percent_uses_idle_and_total_deltas(self) -> None:
        self.assertEqual(cpu_percent((100, 200), (110, 240)), 75.0)

    def test_invalid_counter_delta_is_unavailable(self) -> None:
        self.assertIsNone(cpu_percent((100, 200), (101, 200)))
        self.assertIsNone(cpu_percent((100, 200), (99, 220)))

    def test_summary_contains_only_aggregated_values(self) -> None:
        result = summarize_samples([10.0, 20.0, 30.0], [512.0, 480.0, 500.0], 1.25)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["scope"], "verifier_process")
        self.assertEqual(result["cpu_percent_p95"], 30.0)
        self.assertEqual(result["available_memory_mb_min"], 480.0)
        self.assertNotIn("hostname", result)
        self.assertNotIn("username", result)

    def test_missing_cpu_samples_does_not_claim_available(self) -> None:
        result = summarize_samples([], [512.0], 0.3)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertNotIn("cpu_percent_p95", result)

    def test_reader_failure_is_fixed_and_does_not_echo_exception(self) -> None:
        def fail(_previous):
            raise RuntimeError("synthetic secret-like diagnostic text")

        observer = ResourceObserver(reader=fail, interval_seconds=0.1)
        observer.start()
        time.sleep(0.03)
        result = observer.stop()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertNotIn("synthetic secret-like diagnostic text", repr(result))


    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows host counters required")
    def test_windows_host_counters_are_read_only_and_aggregated(self) -> None:
        observer = ResourceObserver(interval_seconds=0.1)
        observer.start()
        time.sleep(0.35)
        result = observer.stop()
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["scope"], "verifier_process")
        self.assertGreaterEqual(result["sample_count"], 2)
        self.assertGreaterEqual(result["cpu_percent_p95"], 0.0)
        self.assertLessEqual(result["cpu_percent_p95"], 100.0)
        self.assertGreater(result["available_memory_mb_min"], 0.0)

    def test_observer_keeps_cpu_and_memory_values_separate(self) -> None:
        reader = Mock(side_effect=[
            ((100, 200), None, 700.0),
            ((110, 240), 75.0, 650.0),
            ((120, 280), 75.0, 600.0),
        ])
        observer = ResourceObserver(reader=reader, interval_seconds=0.1)
        observer.start()
        time.sleep(0.23)
        result = observer.stop()
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["cpu_percent_p95"], 75.0)
        self.assertEqual(result["available_memory_mb_min"], 600.0)


if __name__ == "__main__":
    unittest.main()
