from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.prototype.api.cursors import (
    RequirementPrototypeLinkCursorCodec,
)
from plm_assistant.modules.prototype.api.requirement_links import (
    create_requirement_prototype_link_router,
)
from plm_assistant.modules.prototype.application.requirement_links import (
    RequirementPrototypeCoverage,
    RequirementPrototypeLinkError,
    RequirementPrototypeLinkPage,
    RequirementPrototypeLinkView,
    UncoveredAcceptanceCriterion,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, REQUIREMENT, REQUIREMENT_VERSION, PROTOTYPE, PROTOTYPE_VERSION = (
    uuid.uuid4() for _ in range(5)
)
LINK, REPLACEMENT, ACTOR, COVERED, UNCOVERED = (
    uuid.uuid4() for _ in range(5)
)
COVERAGE = RequirementPrototypeCoverage(
    (COVERED,), (UncoveredAcceptanceCriterion(UNCOVERED, "Deferred"),),
)


def link_view(
    *, identity: uuid.UUID = LINK, state: str = "ACTIVE",
    version: int = 0, superseded_by: uuid.UUID | None = None,
) -> RequirementPrototypeLinkView:
    return RequirementPrototypeLinkView(
        identity, PROJECT, REQUIREMENT, REQUIREMENT_VERSION,
        PROTOTYPE, PROTOTYPE_VERSION, "ILLUSTRATES", COVERAGE,
        state, version, ACTOR, NOW, superseded_by,
    )


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Service:
    fail = None
    malformed = False

    def _check(self):
        if self.fail:
            raise RequirementPrototypeLinkError(self.fail)

    def list(self, query, *, page_size, after_link_id=None):
        self.query, self.after = query, after_link_id
        self._check()
        if self.malformed:
            return RequirementPrototypeLinkPage((link_view(),), None, True)
        return RequirementPrototypeLinkPage(
            (link_view(),), LINK if after_link_id is None else None,
            after_link_id is None,
        )

    def create(self, command):
        self.command = command
        self._check()
        return link_view()

    def revoke(self, command):
        self.command = command
        self._check()
        return link_view(state="REVOKED", version=1)

    def supersede(self, command):
        self.command = command
        self._check()
        return link_view(identity=REPLACEMENT)


class RequirementPrototypeLinkApiTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.service.fail, self.service.malformed = None, False
        router = create_requirement_prototype_link_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            service=self.service,
            cursors=RequirementPrototypeLinkCursorCodec(b"l" * 32),
        )
        self.client = TestClient(create_app(
            requirement_prototype_link_router=router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/prototype-requirement-links"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers,
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
        }
        self.body = {
            "requirement_id": str(REQUIREMENT),
            "requirement_version_id": str(REQUIREMENT_VERSION),
            "prototype_id": str(PROTOTYPE),
            "prototype_version_id": str(PROTOTYPE_VERSION),
            "purpose": "ILLUSTRATES",
            "coverage": {
                "covered_acceptance_criterion_refs": [str(COVERED)],
                "uncovered_acceptance_criteria": [{
                    "acceptance_criterion_ref": str(UNCOVERED),
                    "reason": "Deferred",
                }],
            },
        }

    def test_default_closed_and_four_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in (
                ("get", self.root), ("post", self.root),
                ("post", f"{self.root}/{LINK}:revoke"),
                ("post", f"{self.root}/{LINK}:supersede"),
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
        self.assertEqual(LINK, self.service.after)
        self.assertFalse(second.json()["data"]["has_more"])

        created = self.client.post(
            self.root, headers=self.write_headers, json=self.body,
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual("ILLUSTRATES", created.json()["data"]["purpose"])

        revoked = self.client.post(
            f"{self.root}/{LINK}:revoke", headers=self.write_headers,
        )
        self.assertEqual(200, revoked.status_code)
        self.assertEqual('"v1"', revoked.headers["etag"])
        self.assertEqual(0, self.service.command.expected_version)

        replaced = self.client.post(
            f"{self.root}/{LINK}:supersede",
            headers=self.write_headers, json=self.body,
        )
        self.assertEqual(201, replaced.status_code)
        self.assertEqual(str(REPLACEMENT), replaced.json()["data"]
                         ["requirement_prototype_link_id"])
        self.assertEqual(0, self.service.command.expected_version)

    def test_security_json_cursor_and_output_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.write_headers,
                                "origin": "https://evil.test"},
            json=self.body,
        ).status_code)
        no_key = {key: value for key, value in self.write_headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            f"{self.root}/{LINK}:revoke", headers=no_key,
        ).status_code)
        self.assertEqual(400, self.client.post(
            f"{self.root}/{LINK}:revoke", headers=self.write_headers,
            content=b"{}",
        ).status_code)
        malformed = dict(self.body)
        malformed["coverage"] = {"covered_acceptance_criterion_refs": []}
        self.assertEqual(400, self.client.post(
            self.root, headers=self.write_headers, json=malformed,
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1", headers=self.read_headers,
        ).status_code)
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        other = (f"/api/v1/projects/{uuid.uuid4()}/prototype-requirement-links"
                 f"?page_size=1&cursor={first.json()['data']['next_cursor']}")
        self.assertEqual(400, self.client.get(
            other, headers=self.read_headers,
        ).status_code)
        self.service.malformed = True
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers,
        ).status_code)

    def test_safe_error_mapping(self):
        for code, action, status in (
            ("AUTH_ACCESS_DENIED", "list", 404),
            ("LICENSE_OPERATION_DENIED", "list", 403),
            ("COVERAGE_INCOMPLETE", "create", 422),
            ("PROTOTYPE_INPUT_DRIFT", "create", 422),
            ("LINK_CONFLICT", "create", 409),
            ("CONFLICT_IDEMPOTENCY", "revoke", 409),
            ("SYSTEM_UNAVAILABLE", "supersede", 503),
        ):
            with self.subTest(code=code):
                self.service.fail = code
                if action == "list":
                    response = self.client.get(self.root, headers=self.read_headers)
                elif action == "create":
                    response = self.client.post(
                        self.root, headers=self.write_headers, json=self.body,
                    )
                elif action == "revoke":
                    response = self.client.post(
                        f"{self.root}/{LINK}:revoke", headers=self.write_headers,
                    )
                else:
                    response = self.client.post(
                        f"{self.root}/{LINK}:supersede",
                        headers=self.write_headers, json=self.body,
                    )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                self.service.fail = None


if __name__ == "__main__":
    unittest.main()
