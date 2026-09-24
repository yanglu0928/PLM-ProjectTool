from __future__ import annotations

import io
import json
import unittest

from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


TRACE_ID = "018f0000-0000-7000-8000-000000000001"


class StructuredLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_stream = io.StringIO()
        self.integration_stream = io.StringIO()
        self.loggers = StructuredLoggers(
            application_stream=self.app_stream,
            integration_stream=self.integration_stream,
        )

    def test_application_log_has_only_allowlisted_json_fields(self) -> None:
        self.loggers.application(
            event="request_failed",
            component="platform.api",
            level="ERROR",
            trace_id=TRACE_ID,
            error_code="SYSTEM_INTERNAL",
            duration_ms=9,
        )
        record = json.loads(self.app_stream.getvalue())
        self.assertEqual(record["category"], "application")
        self.assertEqual(record["trace_id"], TRACE_ID)
        self.assertEqual(record["error_code"], "SYSTEM_INTERNAL")
        self.assertEqual(record["duration_ms"], 9)
        self.assertEqual(
            set(record),
            {"timestamp", "category", "level", "component", "event", "trace_id", "error_code", "duration_ms"},
        )
        self.assertEqual(self.integration_stream.getvalue(), "")

    def test_integration_log_is_separate_and_redacted(self) -> None:
        self.loggers.integration(
            event="integration_finished",
            integration_type="ai",
            provider="deepseek",
            trace_id=TRACE_ID,
            outcome="FAILURE",
            duration_ms=23,
            retryable=True,
            invocation_id=TRACE_ID,
            error_code="SYSTEM_UNAVAILABLE",
        )
        record = json.loads(self.integration_stream.getvalue())
        self.assertEqual(record["category"], "integration")
        self.assertEqual(record["provider"], "deepseek")
        self.assertEqual(record["outcome"], "FAILURE")
        self.assertEqual(record["retryable"], True)
        self.assertEqual(self.app_stream.getvalue(), "")
        self.assertNotIn("request", record)
        self.assertNotIn("response", record)

    def test_unregistered_or_sensitive_values_cannot_be_logged(self) -> None:
        bad_calls = (
            lambda: self.loggers.application(
                event="password=private", component="platform.api"
            ),
            lambda: self.loggers.application(
                event="request_failed", component="C:/customer/path"
            ),
            lambda: self.loggers.application(
                event="request_failed", component="platform.api", trace_id="secret"
            ),
            lambda: self.loggers.integration(
                event="integration_finished", integration_type="ai",
                provider="sk-secret-key-value", trace_id=TRACE_ID,
                outcome="FAILURE", duration_ms=1, retryable=False,
            ),
        )
        for call in bad_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        self.assertEqual(self.app_stream.getvalue(), "")
        self.assertEqual(self.integration_stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
