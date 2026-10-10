from __future__ import annotations

import unittest
import uuid

from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.application.errors import ApplicationError


class InputDto(BaseModel):
    count: int


def make_test_app():
    app = create_app()

    @app.get("/api/v1/test/classified")
    def classified() -> None:
        raise ApplicationError("CONFLICT_VERSION")

    @app.get("/api/v1/test/internal")
    def internal() -> None:
        raise RuntimeError("password=private; SQLSTATE 23505; C:/secret/file")

    @app.get("/api/v1/test/hidden")
    def hidden() -> None:
        raise HTTPException(status_code=403, detail="project 123 exists")

    @app.get("/api/v1/test/csrf")
    def csrf() -> None:
        raise ApplicationError("AUTH_CSRF_INVALID")

    @app.post("/api/v1/test/validate")
    def validate(payload: InputDto = Body()) -> dict[str, int]:
        return {"count": payload.count}

    return app


class ErrorApiTests(unittest.TestCase):
    def assert_envelope(self, response, *, status: int, code: str) -> None:
        self.assertEqual(response.status_code, status)
        data = response.json()
        self.assertEqual(set(data), {"error", "trace_id"})
        self.assertEqual(set(data["error"]), {"code", "message", "details"})
        self.assertEqual(data["error"]["code"], code)
        self.assertEqual(data["error"]["details"], [])
        self.assertEqual(response.headers["x-trace-id"], data["trace_id"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(str(uuid.UUID(data["trace_id"])), data["trace_id"])

    def test_classified_conflict_uses_frozen_code(self) -> None:
        with TestClient(make_test_app()) as client:
            response = client.get("/api/v1/test/classified")
        self.assert_envelope(response, status=409, code="CONFLICT_VERSION")

    def test_internal_error_never_exposes_exception(self) -> None:
        with TestClient(make_test_app(), raise_server_exceptions=False) as client:
            response = client.get("/api/v1/test/internal")
        self.assert_envelope(response, status=500, code="SYSTEM_INTERNAL")
        for secret in ("password", "private", "SQLSTATE", "secret/file"):
            self.assertNotIn(secret, response.text)

    def test_permission_error_uses_indistinguishable_404(self) -> None:
        with TestClient(make_test_app()) as client:
            hidden = client.get("/api/v1/test/hidden")
            absent = client.get("/api/v1/test/absent")
        self.assert_envelope(hidden, status=404, code="RESOURCE_NOT_FOUND")
        self.assert_envelope(absent, status=404, code="RESOURCE_NOT_FOUND")
        self.assertEqual(hidden.json()["error"], absent.json()["error"])
        self.assertNotIn("project 123", hidden.text)

    def test_classified_csrf_failure_remains_403(self) -> None:
        with TestClient(make_test_app()) as client:
            response = client.get("/api/v1/test/csrf")
        self.assert_envelope(response, status=403, code="AUTH_CSRF_INVALID")

    def test_validation_discards_raw_input(self) -> None:
        with TestClient(make_test_app()) as client:
            response = client.post(
                "/api/v1/test/validate", json={"count": "customer-secret"}
            )
        self.assert_envelope(response, status=422, code="VALIDATION_FAILED")
        self.assertNotIn("customer-secret", response.text)

    def test_malformed_json_is_400(self) -> None:
        with TestClient(make_test_app()) as client:
            response = client.post(
                "/api/v1/test/validate",
                content=b'{"count":',
                headers={"content-type": "application/json"},
            )
        self.assert_envelope(response, status=400, code="REQUEST_MALFORMED")

    def test_trace_header_is_reused_only_when_canonical(self) -> None:
        supplied = "018f0000-0000-7000-8000-000000000001"
        with TestClient(make_test_app()) as client:
            valid = client.get(
                "/api/v1/test/classified", headers={"x-trace-id": supplied}
            )
            invalid = client.get(
                "/api/v1/test/classified", headers={"x-trace-id": supplied.upper()}
            )
        self.assertEqual(valid.json()["trace_id"], supplied)
        self.assertNotEqual(invalid.json()["trace_id"], supplied.upper())
        self.assertEqual(uuid.UUID(invalid.json()["trace_id"]).version, 7)

    def test_method_not_allowed_has_safe_envelope(self) -> None:
        with TestClient(make_test_app()) as client:
            response = client.delete("/api/v1/test/validate")
        self.assert_envelope(
            response, status=405, code="REQUEST_METHOD_NOT_ALLOWED"
        )


if __name__ == "__main__":
    unittest.main()
