from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.evidence.application.create_access import (
    EvidenceCreateAccess, EvidenceCreateAccessError,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Session:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor
        self.calls: list[dict] = []

    def authenticated_user(self, transaction, **kwargs):
        self.calls.append(kwargs)
        return self.actor


class _Admin:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor
        self.calls = 0

    def authorized_admin(self, transaction, **kwargs):
        self.calls += 1
        return self.actor


class _Facts:
    def __init__(self) -> None:
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.calls: list[dict] = []

    def actor_facts(self, transaction, **kwargs):
        self.calls.append(kwargs)
        return ProjectActorFacts(self.state, self.role) if self.role else None


class EvidenceCreateAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = uuid.uuid4()
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()
        self.session = _Session(self.actor)
        self.admin = _Admin(self.actor)
        self.facts = _Facts()
        self.access = EvidenceCreateAccess(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            session_access=self.session, admin_access=self.admin,
            project_facts=self.facts,
            clock=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc),
        )

    def require(self, *, scope: str = "PROJECT", project_id=None,
                document_id=None, operation: str = "V1_EVIDENCE_CREATE") -> None:
        self.access.require_in_transaction(
            object(), actor_id=self.actor, scope=scope,
            project_id=self.project if project_id is None and scope == "PROJECT" else project_id,
            document_id=self.document if document_id is None else document_id,
            operation=operation,
        )

    def test_project_role_matrix_and_live_lock(self) -> None:
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"):
            with self.subTest(role=role):
                self.facts.role = role
                self.require()
                self.assertEqual(self.facts.calls[-1], {
                    "user_id": self.actor, "project_id": self.project, "lock": True,
                })
        for role in ("CUSTOMER_MANAGER", "CUSTOMER_MEMBER", None):
            with self.subTest(role=role):
                self.facts.role = role
                with self.assertRaises(EvidenceCreateAccessError) as caught:
                    self.require()
                self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_archived_project_and_session_revocation_fail(self) -> None:
        self.facts.state = "ARCHIVED"
        with self.assertRaises(EvidenceCreateAccessError) as caught:
            self.require()
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.facts.state = "ACTIVE"
        self.session.actor = None
        with self.assertRaises(EvidenceCreateAccessError) as caught:
            self.require()
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.session.actor = uuid.uuid4()
        with self.assertRaises(EvidenceCreateAccessError):
            self.require()

    def test_global_requires_current_admin_and_never_queries_project(self) -> None:
        self.require(scope="GLOBAL")
        self.assertEqual(self.admin.calls, 1)
        self.assertEqual(self.facts.calls, [])
        self.admin.actor = None
        with self.assertRaises(EvidenceCreateAccessError) as caught:
            self.require(scope="GLOBAL")
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")

    def test_spoofed_scope_document_operation_and_tokens_fail(self) -> None:
        invalid = [
            {"scope": "GLOBAL", "project_id": self.project},
            {"scope": "TENANT"},
            {"document_id": uuid.UUID(int=0)},
            {"operation": "V1_EVIDENCE_SET_ELIGIBILITY"},
        ]
        for change in invalid:
            with self.subTest(change=change):
                with self.assertRaises(EvidenceCreateAccessError) as caught:
                    self.require(**change)
                self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        with self.assertRaises(EvidenceCreateAccessError):
            self.access.require_in_transaction(
                object(), actor_id=self.actor, scope="PROJECT", project_id=None,
                document_id=self.document, operation="V1_EVIDENCE_CREATE",
            )
        for token in (b"short", "x" * 32):
            with self.assertRaises(ValueError):
                EvidenceCreateAccess(
                    session_token=token, csrf_token=b"c" * 32,
                    session_access=self.session, admin_access=self.admin,
                    project_facts=self.facts,
                )
        self.require()
        self.assertEqual(self.session.calls[-1]["csrf_token"], b"c" * 32)


if __name__ == "__main__":
    unittest.main()
