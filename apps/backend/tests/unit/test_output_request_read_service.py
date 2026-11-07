from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.output.application.read_request import (
    OutputRequestReadError, OutputRequestReadQuery, OutputRequestReadService,
    OutputRequestView,
)


class UnitOfWork:
    @contextmanager
    def __call__(self):
        yield object()


class Access:
    def __init__(self, user_id):
        self.user_id = user_id

    def authenticated_user(self, transaction, *, session_token, now):
        del transaction, session_token, now
        return self.user_id


class Projects:
    def __init__(self, authorized=True):
        self.authorized = authorized
        self.calls = []

    def get_authorized(self, transaction, user_id, project_id):
        self.calls.append((transaction, user_id, project_id))
        return object() if self.authorized else None


class License:
    def require_valid(self, *, trace_id):
        self.trace_id = trace_id


class Repository:
    def __init__(self, view=None, error=None):
        self.view, self.error, self.calls = view, error, []

    def get(self, transaction, *, project_id, output_request_id):
        self.calls.append((transaction, project_id, output_request_id))
        if self.error:
            raise self.error
        return self.view


class OutputRequestReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.project_id, self.request_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.trace_id = uuid.uuid4()
        self.token = bytes.fromhex("42" * 32)
        self.view = OutputRequestView(
            output_request_id=self.request_id, project_id=self.project_id,
            output_type="DOCX", template_version_ref=uuid.uuid4(),
            source_version_refs=(uuid.uuid4(),), output_policy_ref="output.policy.v1",
            plugin_operation="word.generate", context_snapshot_ref=uuid.uuid4(),
            context_fingerprint=bytes.fromhex("bc" * 32), request_state="REQUESTED",
            job_ref=None, execution_ref=None, generation_no=1,
            requested_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
            completed_at=None, lock_version=0,
        )
        self.projects = Projects()
        self.repository = Repository(self.view)
        self.license = License()
        self.service = OutputRequestReadService(
            unit_of_work=UnitOfWork(), access=Access(self.user_id),
            projects=self.projects, license_guard=self.license,
            repository=self.repository,
            clock=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc),
        )

    def test_requires_project_membership_and_returns_fixed_request_projection(self):
        result = self.service.get(
            OutputRequestReadQuery(self.token, self.trace_id),
            project_id=self.project_id, output_request_id=self.request_id,
        )
        self.assertIs(result, self.view)
        self.assertEqual(self.projects.calls[0][1:], (self.user_id, self.project_id))
        self.assertEqual(
            self.repository.calls[0][1:],
            (self.project_id, self.request_id),
        )
        self.assertEqual(self.license.trace_id, self.trace_id)

    def test_nonmember_and_unknown_request_have_indistinguishable_not_found(self):
        self.projects.authorized = False
        with self.assertRaises(OutputRequestReadError) as caught:
            self.service.get(
                OutputRequestReadQuery(self.token, self.trace_id),
                project_id=self.project_id, output_request_id=self.request_id,
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repository.calls, [])

    def test_repository_failure_is_projected_to_safe_system_error(self):
        self.repository.error = RuntimeError("private database detail")
        with self.assertRaises(OutputRequestReadError) as caught:
            self.service.get(
                OutputRequestReadQuery(self.token, self.trace_id),
                project_id=self.project_id, output_request_id=self.request_id,
            )
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
        self.assertNotIn("private database detail", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
