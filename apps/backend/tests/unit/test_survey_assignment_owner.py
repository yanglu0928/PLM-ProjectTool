from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.assignment_views import SurveyAssignmentView
from plm_assistant.modules.survey.application.create_assignment import (
    CreateSurveyAssignment, SurveyAssignmentCreateService,
)
from plm_assistant.modules.survey.application.read_assignments import (
    SurveyAssignmentReadQuery, SurveyAssignmentReadService,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
ACTOR, PROJECT, ROUND, SURVEY, VERSION, DEPARTMENT, ASSIGNMENT = (
    uuid.uuid4() for _ in range(7)
)


def view(assignment_id=ASSIGNMENT):
    return SurveyAssignmentView(
        assignment_id, ROUND, SURVEY, VERSION, PROJECT, DEPARTMENT, None,
        "ASSIGNED", None, None, None, None, None, None, None, ACTOR, NOW,
        None, NOW,
    )


class Tx:
    commits = 0
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs): return ACTOR


class Guard:
    def require_valid(self, **kwargs): return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, kwargs["operation"], "PROJECT_MANAGER",
        )


class Repository:
    def create(self, transaction, **kwargs): return view(kwargs["survey_assignment_id"])
    def get_initial(self, transaction, **kwargs): return view(kwargs["survey_assignment_id"])
    def list_assignments(self, transaction, **kwargs): return (view(),)
    def get_assignment(self, transaction, **kwargs): return view()


class Receipts:
    replay = None
    completed = []
    def reserve(self, transaction, **kwargs): return self.replay
    def complete(self, transaction, **kwargs): self.completed.append(kwargs["result"])


class Audit:
    events = []
    def append(self, transaction, event): self.events.append(event); return uuid.uuid4()


class SurveyAssignmentOwnerTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0; Receipts.replay = None; Receipts.completed = []; Audit.events = []
        self.receipts = Receipts()
        self.create = SurveyAssignmentCreateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(),
            receipts=self.receipts, audit=Audit(), clock=lambda: NOW,
        )
        self.command = CreateSurveyAssignment(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ROUND, DEPARTMENT,
            None, str(uuid.uuid4()),
        )

    def test_create_is_atomic_audited_and_receipted(self):
        result = self.create.create(self.command)
        self.assertEqual("ASSIGNED", result.submission_state)
        self.assertEqual(1, Tx.commits)
        self.assertEqual("SURVEY_ASSIGNMENT_CREATED", Audit.events[0].action)
        receipt = Receipts.completed[0]
        self.assertEqual("V1_SURVEY_ASSIGNMENT_CREATE", receipt.ref_type)
        self.assertEqual(result.survey_assignment_id, receipt.ref_id)
        self.assertEqual(201, receipt.status_code)

    def test_reads_pass_actor_role_and_paginate(self):
        reads = SurveyAssignmentReadService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(), clock=lambda: NOW,
        )
        query = SurveyAssignmentReadQuery(b"s" * 32, uuid.uuid4(), PROJECT, ROUND)
        page = reads.list_assignments(query, page_size=10)
        self.assertEqual((view(),), page.items)
        self.assertEqual(view(), reads.get_assignment(query, ASSIGNMENT))

    def test_secrets_are_not_rendered(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__": unittest.main()
