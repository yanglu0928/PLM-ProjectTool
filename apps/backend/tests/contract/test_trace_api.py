from __future__ import annotations

import asyncio
import io
import json
import unittest
import uuid

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.trace_context import current_trace_id
from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


TRACE_A = "018f0000-0000-7000-8000-000000000001"
TRACE_B = "018f0000-0000-7000-8000-000000000002"


class TraceApiTests(unittest.TestCase):
    def make_app(self):
        application_stream = io.StringIO()
        app = create_app(
            loggers=StructuredLoggers(
                application_stream=application_stream,
                integration_stream=io.StringIO(),
            )
        )

        @app.get("/api/v1/test/trace")
        def trace(request: Request) -> JSONResponse:
            value = current_trace_id()
            return JSONResponse(
                {
                    "data": {
                        "bound_trace": value,
                        "request_trace": request.state.trace_id,
                    },
                    "trace_id": value,
                },
                headers={"X-Trace-Id": TRACE_B},
            )

        @app.get("/api/v1/test/failed")
        def failed() -> None:
            raise ApplicationError("CONFLICT_STATE")

        @app.get("/api/v1/test/crash")
        def crash() -> None:
            raise RuntimeError("password=private")

        return app, application_stream

    def test_success_health_and_log_share_valid_client_trace(self) -> None:
        app, stream = self.make_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/test/trace", headers={"X-Trace-Id": TRACE_A}
            )
            health = client.get("/health/live", headers={"X-Trace-Id": TRACE_A})
        self.assertEqual(response.json()["trace_id"], TRACE_A)
        self.assertEqual(response.json()["data"]["bound_trace"], TRACE_A)
        self.assertEqual(response.json()["data"]["request_trace"], TRACE_A)
        self.assertEqual(response.headers["x-trace-id"], TRACE_A)
        self.assertEqual(health.json(), {"status": "UP"})
        self.assertEqual(health.headers["x-trace-id"], TRACE_A)
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["trace_id"] == TRACE_A for record in records))
        self.assertTrue(all(record["status_code"] == 200 for record in records))
        self.assertTrue(all(record["duration_ms"] >= 0 for record in records))
        self.assertIsNone(current_trace_id())

    def test_invalid_and_duplicate_headers_generate_uuid7(self) -> None:
        app, _ = self.make_app()
        with TestClient(app) as client:
            invalid = client.get(
                "/api/v1/test/trace", headers={"X-Trace-Id": TRACE_A.upper()}
            )
            duplicate = client.get(
                "/api/v1/test/trace",
                headers=[("X-Trace-Id", TRACE_A), ("X-Trace-Id", TRACE_B)],
            )
        for response in (invalid, duplicate):
            self.assertEqual(response.status_code, 200)
            trace_id = response.json()["trace_id"]
            self.assertEqual(uuid.UUID(trace_id).version, 7)
            self.assertNotIn(trace_id, {TRACE_A, TRACE_B})
            self.assertEqual(response.headers["x-trace-id"], trace_id)

    def test_error_response_uses_same_trace_as_request_and_logs(self) -> None:
        app, stream = self.make_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            classified = client.get(
                "/api/v1/test/failed", headers={"X-Trace-Id": TRACE_A}
            )
            unknown = client.get(
                "/api/v1/test/crash", headers={"X-Trace-Id": TRACE_B}
            )
        self.assertEqual(classified.status_code, 409)
        self.assertEqual(classified.json()["trace_id"], TRACE_A)
        self.assertEqual(classified.headers["x-trace-id"], TRACE_A)
        self.assertEqual(unknown.status_code, 500)
        self.assertEqual(unknown.json()["trace_id"], TRACE_B)
        self.assertEqual(unknown.headers["x-trace-id"], TRACE_B)
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertTrue(any(r["trace_id"] == TRACE_A and r["status_code"] == 409 for r in records))
        self.assertTrue(any(r["trace_id"] == TRACE_B and r["error_code"] == "SYSTEM_INTERNAL" for r in records))
        self.assertNotIn("private", stream.getvalue())

    def test_parallel_requests_keep_isolated_trace_context(self) -> None:
        app, _ = self.make_app()

        @app.get("/api/v1/test/async-trace")
        async def async_trace() -> dict[str, str | None]:
            before = current_trace_id()
            await asyncio.sleep(0.01)
            return {"before": before, "after": current_trace_id()}

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                return await asyncio.gather(
                    client.get("/api/v1/test/async-trace", headers={"X-Trace-Id": TRACE_A}),
                    client.get("/api/v1/test/async-trace", headers={"X-Trace-Id": TRACE_B}),
                )

        first, second = asyncio.run(run())
        self.assertEqual(first.json(), {"before": TRACE_A, "after": TRACE_A})
        self.assertEqual(second.json(), {"before": TRACE_B, "after": TRACE_B})
        self.assertEqual(first.headers["x-trace-id"], TRACE_A)
        self.assertEqual(second.headers["x-trace-id"], TRACE_B)
        self.assertIsNone(current_trace_id())

    def test_streaming_response_keeps_trace_until_body_is_sent(self) -> None:
        app, stream = self.make_app()

        @app.get("/api/v1/test/stream")
        async def stream_trace() -> StreamingResponse:
            async def body():
                await asyncio.sleep(0)
                yield f"data: {current_trace_id()}\n\n"

            return StreamingResponse(body(), media_type="text/event-stream")

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/test/stream", headers={"X-Trace-Id": TRACE_A}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-trace-id"], TRACE_A)
        self.assertEqual(response.text, f"data: {TRACE_A}\n\n")
        self.assertEqual(json.loads(stream.getvalue())["trace_id"], TRACE_A)


if __name__ == "__main__":
    unittest.main()
