from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.output.application.list_requests import (
    OutputRequestListError, OutputRequestListQuery, OutputRequestListService,
)
from plm_assistant.modules.output.application.read_request import OutputRequestView
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
)


class Uow:
    @contextmanager
    def __call__(self):
        yield object()


class Access:
    def __init__(self, user_id):
        self.user_id = user_id

    def authenticated_user(self, transaction, *, session_token, now):
        del transaction, session_token, now
        return self.user_id


class Guard:
    def require_valid(self, *, trace_id):
        self.trace_id = trace_id


class Authorization:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def require_in_transaction(self, transaction, *, user_id, project_id,
                               operation, resource_id=None):
        self.calls.append((transaction, user_id, project_id, operation, resource_id))
        if self.error:
            raise self.error


class Repository:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def list_page(self, transaction, *, project_id, after_requested_at,
                  after_request_id, limit):
        self.calls.append((transaction, project_id, after_requested_at,
                           after_request_id, limit))
        return self.rows


class OutputRequestListServiceTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.project_id = uuid.uuid4(), uuid.uuid4()
        self.trace_id = uuid.uuid4()
        self.token = bytes.fromhex("43" * 32)
        self.now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.views = tuple(OutputRequestView(
            output_request_id=uuid.uuid4(), project_id=self.project_id,
            output_type="DOCX", template_version_ref=uuid.uuid4(),
            source_version_refs=(uuid.uuid4(),), output_policy_ref="output.policy.v1",
            plugin_operation="word.generate", context_snapshot_ref=uuid.uuid4(),
            context_fingerprint=bytes.fromhex(f"{i + 1:02x}" * 32),
            request_state="QUEUED", job_ref=uuid.uuid4(), execution_ref=None,
            generation_no=1, requested_at=self.now, completed_at=None,
            lock_version=i,
        ) for i in range(3))
        self.guard = Guard()
        self.authorization = Authorization()
        self.repository = Repository(self.views)
        self.service = OutputRequestListService(
            unit_of_work=Uow(), access=Access(self.user_id),
            license_guard=self.guard, authorization=self.authorization,
            repository=self.repository, clock=lambda: self.now,
        )

    def test_role_authorized_keyset_page_uses_one_extra_row_for_cursor(self):
        page = self.service.list_page(OutputRequestListQuery(
            self.token, self.trace_id, self.project_id, page_size=2,
        ))
        self.assertEqual(page.items, self.views[:2])
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_requested_at, self.views[1].requested_at)
        self.assertEqual(page.next_request_id, self.views[1].output_request_id)
        self.assertEqual(self.authorization.calls[0][1:],
                         (self.user_id, self.project_id, "OUTPUT_REQUEST_LIST", None))
        self.assertEqual(self.repository.calls[0][1:], (
            self.project_id, None, None, 3,
        ))
        self.assertEqual(self.guard.trace_id, self.trace_id)

    def test_project_role_denial_fails_closed_before_output_query(self):
        self.authorization.error = ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        with self.assertRaises(OutputRequestListError) as caught:
            self.service.list_page(OutputRequestListQuery(
                self.token, self.trace_id, self.project_id,
            ))
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repository.calls, [])

    def test_invalid_cursor_position_shape_is_rejected(self):
        with self.assertRaises(OutputRequestListError) as caught:
            self.service.list_page(OutputRequestListQuery(
                self.token, self.trace_id, self.project_id,
                after_requested_at=self.now,
            ))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
