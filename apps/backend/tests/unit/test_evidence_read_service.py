from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.evidence.application.read_evidence import (
    EvidencePage, EvidenceReadError, EvidenceReadQuery,
    EvidenceReadService, EvidenceView,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _Fake:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.project = uuid.uuid4()
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.admin = True
        self.license = True
        self.fail_repository = False
        self.fact_calls = []
        self.row = EvidenceView(
            uuid.uuid4(), "PROJECT", self.project, uuid.uuid4(), uuid.uuid4(),
            {"locator_type": "DOCUMENT"}, b"x" * 32, "全文", None,
            "CANDIDATE", datetime(2026, 10, 1, tzinfo=timezone.utc), '"v0"',
        )

    def authenticated_user(self, _tx, **_kwargs):
        return self.actor

    def authorized_admin(self, _tx, **_kwargs):
        return self.actor if self.admin else None

    def actor_facts(self, _tx, **kwargs):
        self.fact_calls.append(kwargs)
        return ProjectActorFacts(self.state, self.role) if self.role else None

    def require_valid(self, **_kwargs):
        if not self.license:
            raise RuntimeLicenseError("EXPIRED")

    def list(self, _tx, **kwargs):
        if self.fail_repository:
            raise OSError("private failure")
        return EvidencePage((self.row,), None, False)

    def get(self, _tx, **kwargs):
        if self.fail_repository:
            raise OSError("private failure")
        if kwargs["scope"] != self.row.scope or kwargs["project_id"] != self.row.project_id:
            return None
        return self.row if kwargs["evidence_id"] == self.row.evidence_id else None


class EvidenceReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.fake = _Fake()
        self.query = EvidenceReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", self.fake.project)
        self.service = EvidenceReadService(
            unit_of_work=_Tx, session_access=self.fake, admin_access=self.fake,
            project_facts=self.fake, license_guard=self.fake, repository=self.fake,
            clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        )

    def test_all_current_project_members_and_archived_metadata(self):
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                     "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"):
            with self.subTest(role=role):
                self.fake.role = role
                self.assertEqual(self.service.get(self.query, self.fake.row.evidence_id), self.fake.row)
                self.assertEqual(self.service.list(self.query).items, (self.fake.row,))
        self.fake.state = "ARCHIVED"
        self.assertEqual(self.service.get(self.query, self.fake.row.evidence_id), self.fake.row)
        self.assertEqual(self.fake.fact_calls[-1]["project_id"], self.fake.project)

    def test_cross_project_and_removed_member_fail_closed(self):
        wrong = EvidenceReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", uuid.uuid4())
        with self.assertRaisesRegex(EvidenceReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(wrong, self.fake.row.evidence_id)
        self.fake.role = None
        with self.assertRaisesRegex(EvidenceReadError, "RESOURCE_NOT_FOUND"):
            self.service.list(self.query)
        self.fake.role = "CUSTOMER_MEMBER"
        self.fake.state = "SUSPENDED"
        with self.assertRaisesRegex(EvidenceReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(self.query, self.fake.row.evidence_id)

    def test_global_requires_admin_and_does_not_query_project(self):
        global_query = EvidenceReadQuery(b"s" * 32, uuid.uuid4(), "GLOBAL", None)
        self.fake.row = EvidenceView(
            self.fake.row.evidence_id, "GLOBAL", None,
            self.fake.row.document_id, self.fake.row.document_version_id,
            self.fake.row.locator, self.fake.row.content_fingerprint,
            "标准", None, "CANDIDATE", self.fake.row.created_at, '"v0"',
        )
        self.assertEqual(self.service.get(global_query, self.fake.row.evidence_id), self.fake.row)
        self.assertEqual(self.fake.fact_calls, [])
        self.fake.admin = False
        with self.assertRaisesRegex(EvidenceReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(global_query, self.fake.row.evidence_id)

    def test_session_license_and_repository_fail_closed(self):
        self.fake.actor = None
        with self.assertRaisesRegex(EvidenceReadError, "AUTH_ACCESS_DENIED"):
            self.service.list(self.query)
        self.fake.actor = uuid.uuid4()
        self.fake.license = False
        with self.assertRaisesRegex(EvidenceReadError, "LICENSE_OPERATION_DENIED"):
            self.service.list(self.query)
        self.fake.license = True
        self.fake.fail_repository = True
        with self.assertRaisesRegex(EvidenceReadError, "EVIDENCE_UNAVAILABLE"):
            self.service.list(self.query)

    def test_keyset_and_invalid_inputs(self):
        after = (datetime(2026, 10, 1, tzinfo=timezone.utc), uuid.uuid4())
        self.assertEqual(self.service.list(self.query, after=after, limit=1).items,
                         (self.fake.row,))
        for bad in (0, 201, True):
            with self.subTest(limit=bad), self.assertRaisesRegex(EvidenceReadError, "VALIDATION_FAILED"):
                self.service.list(self.query, limit=bad)
        for bad in ((datetime(2026, 10, 1), uuid.uuid4()),
                    (datetime(2026, 10, 1, tzinfo=timezone.utc), uuid.UUID(int=0))):
            with self.subTest(after=bad), self.assertRaisesRegex(EvidenceReadError, "VALIDATION_FAILED"):
                self.service.list(self.query, after=bad)
        with self.assertRaisesRegex(EvidenceReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(self.query, uuid.UUID(int=0))


if __name__ == "__main__":
    unittest.main()
