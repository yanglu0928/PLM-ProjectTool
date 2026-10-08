from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.prototype.api.cursors import PrototypeVersionCursorCodec
from plm_assistant.modules.prototype.api.versions import create_prototype_version_router
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionCreateError,
    PrototypeVersionInitialView,
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeVersionPage,
    PrototypeVersionReadError,
    PrototypeVersionValidationReport,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, PROTOTYPE, VERSION, TEMPLATE, TEMPLATE_VERSION = (
    uuid.uuid4() for _ in range(5)
)
DOCUMENT, REQUIREMENT, REQUIREMENT_VERSION, AUDIT = (
    uuid.uuid4() for _ in range(4)
)


def version_view(*, number: int = 2, identity: uuid.UUID = VERSION) -> PrototypeVersionInitialView:
    return PrototypeVersionInitialView(
        identity, PROTOTYPE, PROJECT, number, None,
        TEMPLATE, TEMPLATE_VERSION,
        (VersionArtifactRef("DOCUMENT_VERSION", DOCUMENT),),
        (VersionRequirementRef(REQUIREMENT, REQUIREMENT_VERSION),),
        {"screens": [{"id": "home"}]},
        {"covered": [str(REQUIREMENT_VERSION)]},
        "ab" * 32, NOW,
    )


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token != b"s" * 32
                or require_csrf and csrf_token != b"c" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None
    malformed = False

    def list(self, query, *, page_size, before_version_no=None):
        self.query, self.before = query, before_version_no
        if self.fail:
            raise PrototypeVersionReadError(self.fail)
        if self.malformed:
            return PrototypeVersionPage((version_view(),), None, True)
        return PrototypeVersionPage(
            (version_view(),), 2 if before_version_no is None else None,
            before_version_no is None,
        )

    def get(self, query, *, version_id):
        self.query = query
        if self.fail:
            raise PrototypeVersionReadError(self.fail)
        return version_view(identity=version_id)

    def validate(self, query, *, version_id, csrf_token, idempotency_key):
        self.query, self.csrf, self.key = query, csrf_token, idempotency_key
        if self.fail:
            raise PrototypeVersionReadError(self.fail)
        return PrototypeVersionValidationReport(
            version_id, False, ("ARTIFACT_UNAVAILABLE",), NOW, "DRAFT",
            AUDIT, uuid.uuid4(),
        )


class Creates:
    fail = None

    def create(self, command):
        self.command = command
        if self.fail:
            raise PrototypeVersionCreateError(self.fail)
        return version_view()


class PrototypeVersionApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates = Reads(), Creates()
        self.reads.fail = self.creates.fail = None
        self.reads.malformed = False
        router = create_prototype_version_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, creates=self.creates,
            cursors=PrototypeVersionCursorCodec(b"v" * 32),
        )
        self.client = TestClient(
            create_app(prototype_version_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/prototypes/{PROTOTYPE}/versions"
        self.detail = f"{self.root}/{VERSION}"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers,
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.body = {
            "template_id": str(TEMPLATE),
            "template_version_id": str(TEMPLATE_VERSION),
            "artifact_refs": [{
                "artifact_kind": "DOCUMENT_VERSION", "target_id": str(DOCUMENT),
            }],
            "requirement_refs": [{
                "requirement_id": str(REQUIREMENT),
                "requirement_version_id": str(REQUIREMENT_VERSION),
            }],
            "interaction_spec": {"screens": [{"id": "home"}]},
            "coverage_summary": {"covered": [str(REQUIREMENT_VERSION)]},
        }

    def test_default_closed_and_four_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in (
                ("get", self.root), ("post", self.root),
                ("get", self.detail), ("post", self.detail + ":validate"),
            ):
                self.assertEqual(404, getattr(bare, method)(path).status_code)

        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers,
        )
        self.assertEqual(2, self.reads.before)
        self.assertFalse(second.json()["data"]["has_more"])

        created = self.client.post(
            self.root, headers=self.write_headers, json=self.body,
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v1"', created.headers["etag"])
        self.assertEqual(self.detail, created.headers["location"])
        self.assertEqual(0, self.creates.command.expected_lock_version)
        self.assertEqual("DOCUMENT_VERSION",
                         created.json()["data"]["artifact_refs"][0]["artifact_kind"])

        detail = self.client.get(self.detail, headers=self.read_headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual(str(REQUIREMENT_VERSION), detail.json()["data"]
                         ["requirement_refs"][0]["requirement_version_id"])

        headers = {key: value for key, value in self.write_headers.items()
                   if key != "if-match"}
        validated = self.client.post(
            self.detail + ":validate", headers=headers,
        )
        self.assertEqual(200, validated.status_code)
        self.assertFalse(validated.json()["data"]["valid"])
        self.assertEqual(["ARTIFACT_UNAVAILABLE"],
                         validated.json()["data"]["blocking_issues"])
        self.assertEqual(str(AUDIT), validated.json()["data"]["audit_event_id"])

    def test_security_body_and_preconditions_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.read_headers, "host": "evil.test"},
        ).status_code)
        no_match = {key: value for key, value in self.write_headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.post(
            self.root, headers=no_match, json=self.body,
        ).status_code)
        no_key = {key: value for key, value in no_match.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.detail + ":validate", headers=no_key,
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.detail + ":validate", headers=no_match, content=b"{}",
        ).status_code)
        malformed = dict(self.body)
        malformed["artifact_refs"] = [{"artifact_kind": "DOCUMENT_VERSION"}]
        self.assertEqual(400, self.client.post(
            self.root, headers=self.write_headers, json=malformed,
        ).status_code)
        self.assertEqual(422, self.client.get(
            self.root + "?page_size=101", headers=self.read_headers,
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1", headers=self.read_headers,
        ).status_code)

    def test_cursor_output_and_errors_are_safe(self):
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        cursor = first.json()["data"]["next_cursor"]
        other = (
            f"/api/v1/projects/{PROJECT}/prototypes/{uuid.uuid4()}/versions"
            f"?page_size=1&cursor={cursor}"
        )
        self.assertEqual(400, self.client.get(
            other, headers=self.read_headers,
        ).status_code)
        self.reads.malformed = True
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers,
        ).status_code)
        self.reads.malformed = False
        for owner, code, method, status in (
            (self.reads, "AUTH_ACCESS_DENIED", "get", 404),
            (self.reads, "LICENSE_OPERATION_DENIED", "get", 403),
            (self.creates, "CONFLICT_VERSION", "create", 409),
            (self.creates, "PROTOTYPE_ARTIFACT_UNAVAILABLE", "create", 404),
            (self.reads, "CONFLICT_IDEMPOTENCY", "validate", 409),
        ):
            with self.subTest(code=code):
                owner.fail = code
                if method == "get":
                    response = self.client.get(self.root, headers=self.read_headers)
                elif method == "create":
                    response = self.client.post(
                        self.root, headers=self.write_headers, json=self.body,
                    )
                else:
                    response = self.client.post(
                        self.detail + ":validate",
                        headers={key: value for key, value in self.write_headers.items()
                                 if key != "if-match"},
                    )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                owner.fail = None


if __name__ == "__main__":
    unittest.main()
