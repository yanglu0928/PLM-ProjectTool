import unittest
from contextlib import contextmanager

from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.api.maintenance_middleware import _requires_admission
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MaintenanceAdmissionError,
)


class FakeAdmission:
    def __init__(self, *, reject=False):
        self.reject = reject
        self.held = False
        self.entries = 0
        self.exits = 0

    @contextmanager
    def admit(self):
        if self.reject:
            raise MaintenanceAdmissionError("MAINTENANCE_ACTIVE")
        self.entries += 1
        self.held = True
        try:
            yield object()
        finally:
            self.held = False
            self.exits += 1


class MaintenanceMiddlewareTests(unittest.TestCase):
    def test_audited_download_gets_are_write_windows(self):
        routes = (
            "/api/v1/projects/p/documents/d/versions/v/content",
            "/api/v1/global/documents/d/versions/v/content",
            "/api/v1/projects/p/audit-exports/e/content",
            "/api/v1/admin/audit-exports/e/content",
        )
        for path in routes:
            with self.subTest(path=path):
                self.assertTrue(_requires_admission({"method": "GET", "path": path}))
        for path in ("/health/live", "/api/v1/projects/p/documents/d",
                     "/api/v1/admin/audit-exports/e", "/api/v1/other/content"):
            with self.subTest(path=path):
                self.assertFalse(_requires_admission({"method": "GET", "path": path}))

    def test_write_gate_covers_body_stream_response_and_background(self):
        gate = FakeAdmission()
        observed = []
        app = create_app(maintenance_admission=gate)

        @app.post("/probe")
        async def write_probe(request: Request, tasks: BackgroundTasks):
            chunks = []
            async for chunk in request.stream():
                observed.append(("body", gate.held))
                chunks.append(chunk)

            async def background():
                observed.append(("background", gate.held))

            async def response():
                observed.append(("response", gate.held))
                yield b"".join(chunks)

            tasks.add_task(background)
            return StreamingResponse(response(), background=tasks)

        with TestClient(app) as client:
            result = client.post("/probe", content=b"synthetic")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"synthetic")
        self.assertTrue(observed)
        self.assertTrue(all(held for _, held in observed), observed)
        self.assertEqual((gate.entries, gate.exits, gate.held), (1, 1, False))

    def test_refusal_before_business_and_safe_methods_bypass(self):
        gate = FakeAdmission(reject=True)
        called = []
        app = create_app(maintenance_admission=gate)

        @app.post("/probe")
        async def write_probe():
            called.append("write")
            return {"ok": True}

        @app.get("/probe")
        async def read_probe():
            called.append("read")
            return {"ok": True}

        with TestClient(app) as client:
            denied = client.post("/probe")
            allowed = client.get("/probe")
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(denied.json()["error"]["code"], "SYSTEM_UNAVAILABLE")
        self.assertEqual(denied.headers["x-trace-id"], denied.json()["trace_id"])
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(called, ["read"])
        self.assertEqual(gate.entries, 0)

    def test_default_app_does_not_require_admission(self):
        app = create_app()

        @app.post("/probe")
        async def write_probe():
            return {"ok": True}

        with TestClient(app) as client:
            self.assertEqual(client.post("/probe").status_code, 200)

    def test_business_failure_releases_admission(self):
        gate = FakeAdmission()
        app = create_app(maintenance_admission=gate)

        @app.post("/boom")
        async def boom():
            self.assertTrue(gate.held)
            raise RuntimeError("synthetic business failure")

        with TestClient(app, raise_server_exceptions=False) as client:
            self.assertEqual(client.post("/boom").status_code, 500)
        self.assertEqual((gate.entries, gate.exits, gate.held), (1, 1, False))


if __name__ == "__main__":
    unittest.main()
