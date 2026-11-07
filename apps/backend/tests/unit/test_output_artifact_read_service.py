from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.output.application.read_artifact import (
    OutputArtifactReadError, OutputArtifactReadQuery, OutputArtifactReadService,
    OutputArtifactReference,
)


class Uow:
    @contextmanager
    def __call__(self):
        yield object()


class Access:
    def authenticated_user(self, transaction, *, session_token, now):
        del transaction, session_token, now
        return USER


class Projects:
    def __init__(self, allowed=True):
        self.allowed = allowed
    def get_authorized(self, transaction, user_id, project_id):
        del transaction, user_id, project_id
        return object() if self.allowed else None


class License:
    def require_valid(self, *, trace_id):
        del trace_id


class Repository:
    def __init__(self, reference):
        self.reference = reference
        self.calls = []
    def get_available(self, transaction, *, project_id, output_request_id):
        self.calls.append((project_id, output_request_id))
        return self.reference


USER = uuid.uuid4()


class OutputArtifactReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.project, self.request = uuid.uuid4(), uuid.uuid4()
        self.reference = OutputArtifactReference(
            uuid.uuid4(), self.request, self.project, uuid.uuid4(), uuid.uuid4(),
            "DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "ab" * 32, 128,
        )
        self.repo = Repository(self.reference)
        self.projects = Projects()
        self.service = OutputArtifactReadService(
            unit_of_work=Uow(), access=Access(), projects=self.projects,
            license_guard=License(), repository=self.repo,
            clock=lambda: datetime(2026, 11, 6, tzinfo=timezone.utc),
        )
        self.query = OutputArtifactReadQuery(bytes.fromhex("51" * 32), uuid.uuid4())

    def test_returns_only_exact_project_request_reference(self):
        found = self.service.get_available(
            self.query, project_id=self.project, output_request_id=self.request,
        )
        self.assertIs(found, self.reference)
        self.assertEqual(self.repo.calls, [(self.project, self.request)])

    def test_nonmember_is_indistinguishable_from_missing_and_does_not_query(self):
        self.projects.allowed = False
        with self.assertRaises(OutputArtifactReadError) as caught:
            self.service.get_available(
                self.query, project_id=self.project, output_request_id=self.request,
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repo.calls, [])

    def test_repository_failure_is_safe(self):
        self.repo.get_available = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("private"))
        with self.assertRaises(OutputArtifactReadError) as caught:
            self.service.get_available(
                self.query, project_id=self.project, output_request_id=self.request,
            )
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
        self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
