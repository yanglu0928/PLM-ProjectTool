from __future__ import annotations

import io
import json
import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


class ErrorLoggingTests(unittest.TestCase):
    def test_unclassified_failure_logs_only_safe_code_and_matching_trace(self) -> None:
        application_stream = io.StringIO()
        integration_stream = io.StringIO()
        app = create_app(
            loggers=StructuredLoggers(
                application_stream=application_stream,
                integration_stream=integration_stream,
            )
        )

        @app.get("/api/v1/test/internal")
        def fail() -> None:
            raise RuntimeError("password=private SQLSTATE 23505 C:/customer/file")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/test/internal")

        record = json.loads(application_stream.getvalue())
        self.assertEqual(response.status_code, 500)
        self.assertEqual(record["error_code"], "SYSTEM_INTERNAL")
        self.assertEqual(record["trace_id"], response.json()["trace_id"])
        self.assertNotIn("password", application_stream.getvalue())
        self.assertNotIn("SQLSTATE", application_stream.getvalue())
        self.assertNotIn("C:/customer", application_stream.getvalue())
        self.assertEqual(integration_stream.getvalue(), "")

    def test_log_sink_failure_keeps_safe_error_response(self) -> None:
        class FailingStream:
            def write(self, value: str) -> None:
                raise OSError("C:/private/log/path")

            def flush(self) -> None:
                raise OSError("C:/private/log/path")

        app = create_app(
            loggers=StructuredLoggers(application_stream=FailingStream())
        )

        @app.get("/api/v1/test/internal")
        def fail() -> None:
            raise RuntimeError("secret-value")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/test/internal")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "SYSTEM_INTERNAL")
        self.assertNotIn("private", response.text)
        self.assertNotIn("secret-value", response.text)


if __name__ == "__main__":
    unittest.main()
