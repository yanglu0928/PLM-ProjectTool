"""Workflow start command authorization, replay and fail-closed behavior."""

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.workflow.application.read_workflow import (
    ChecklistView, StageView, WorkflowView,
)
from plm_assistant.modules.workflow.application.start_errors import WorkflowStartRepositoryError
from plm_assistant.modules.workflow.application.start_workflow import (
    StartWorkflow, WorkflowStartError, WorkflowStartService,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition


class Tx:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.state["commits"] += 1


class Access:
    def __init__(self, state):
        self.state = state

    def authenticated_user(self, *_args, **_kwargs):
        self.state["auth"] += 1
        return self.state["actor"] if self.state["session_valid"] else None


class Projects:
    def __init__(self, state):
        self.state = state

    def require_in_transaction(self, _tx, **kwargs):
        self.state["authz"] += 1
        if not self.state["pm"]:
            raise ValueError("denied")
        return AuthorizedProjectAction(kwargs["user_id"], kwargs["project_id"],
                                       kwargs["operation"], "PROJECT_MANAGER")


class Guard:
    def __init__(self, state):
        self.state = state

    def require_valid(self, **_kwargs):
        self.state["licenses"] += 1


class Starter:
    def __init__(self, state):
        self.state = state

    def start(self, _tx, **kwargs):
        self.state["starts"] += 1
        if self.state["repo_error"]:
            raise WorkflowStartRepositoryError(self.state["repo_error"])
        return self.state["view"]


class Reader:
    def __init__(self, state):
        self.state = state

    def get(self, _tx, project_id):
        self.state["reads"] += 1
        return self.state["current"]


class Receipts:
    def __init__(self, state):
        self.state = state

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.state["reserves"] += 1
        if self.state["receipt"] is None:
            self.state["fingerprint"] = request_fingerprint
            return None
        if request_fingerprint != self.state["fingerprint"]:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return self.state["receipt"]

    def complete(self, _tx, *, scope, result):
        self.state["completes"] += 1
        self.state["receipt"] = result


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["audits"] += 1
        self.state["event"] = event


def initial_view(project_id):
    definition = six_stage_definition(1)
    stages = tuple(StageView(stage.stage_key, stage.order,
                             "ACTIVE" if index == 0 else "NOT_STARTED",
                             tuple(ChecklistView(item.item_key, item.required, "PENDING")
                                   for item in stage.checklist_items))
                   for index, stage in enumerate(definition.stages))
    return WorkflowView(uuid.uuid4(), project_id, 1, "ACTIVE", "HANDOVER", stages, 1)


class WorkflowStartServiceTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.state = {"commits": 0, "actor": uuid.uuid4(), "session_valid": True,
                      "pm": True, "licenses": 0, "auth": 0, "authz": 0,
                      "starts": 0, "reads": 0, "reserves": 0, "completes": 0,
                      "audits": 0, "repo_error": None, "receipt": None,
                      "fingerprint": None}
        self.state["view"] = initial_view(self.project_id)
        self.state["current"] = self.state["view"]
        self.command = StartWorkflow(b"s" * 32, b"c" * 32, self.project_id,
                                     uuid.uuid4(), 0)
        self.service = WorkflowStartService(
            unit_of_work=lambda: Tx(self.state), sessions=Access(self.state),
            projects=Projects(self.state), license_guard=Guard(self.state),
            starter=Starter(self.state), reader=Reader(self.state),
            receipts=Receipts(self.state), audit=Audit(self.state),
            clock=lambda: datetime(2026, 10, 2, tzinfo=timezone.utc),
        )

    def start(self, command=None, key="workflow-start-123456"):
        return self.service.start(command or self.command, idempotency_key=key)

    def assert_error(self, code, command=None, key="workflow-start-123456"):
        with self.assertRaises(WorkflowStartError) as caught:
            self.start(command, key)
        self.assertEqual(caught.exception.code, code)

    def test_first_start_commits_one_audit_and_receipt(self):
        first = self.start()
        self.assertEqual(first, self.state["view"])
        self.assertEqual(self.state["commits"], 1)
        self.assertEqual(self.state["auth"], 2)
        self.assertEqual(self.state["licenses"], 1)
        self.assertEqual(self.state["authz"], 1)
        self.assertEqual(self.state["starts"], 1)
        self.assertEqual(self.state["audits"], 1)
        self.assertEqual(self.state["completes"], 1)
        self.assertEqual(self.state["event"].action, "WORKFLOW_STARTED")

    def test_replay_returns_first_view_not_changed_live_view(self):
        first = self.start()
        self.state["current"] = WorkflowView(
            first.workflow_id, first.project_id, 1, "ACTIVE", "SURVEY",
            tuple(StageView(stage.stage_key, stage.order,
                            "COMPLETED" if index == 0 else "ACTIVE" if index == 1
                            else "NOT_STARTED", stage.checklist_items)
                  for index, stage in enumerate(first.stages)), 2,
        )
        replay = self.start()
        self.assertEqual(replay, first)
        self.assertEqual(self.state["starts"], 1)
        self.assertEqual(self.state["audits"], 1)
        self.assertEqual(self.state["commits"], 1)

    def test_different_payload_same_key_rejected(self):
        self.start()
        self.assert_error("CONFLICT_IDEMPOTENCY", StartWorkflow(
            b"s" * 32, b"c" * 32, self.project_id, uuid.uuid4(), 1))
        self.assertEqual(self.state["starts"], 1)

    def test_bad_session_never_exposes_license_or_writes(self):
        self.state["session_valid"] = False
        self.assert_error("AUTH_ACCESS_DENIED")
        self.assertEqual(self.state["licenses"], 0)
        self.assertEqual(self.state["starts"], 0)

    def test_denied_pm_never_starts(self):
        self.state["pm"] = False
        self.assert_error("WORKFLOW_UNAVAILABLE")
        self.assertEqual(self.state["starts"], 0)
        self.assertEqual(self.state["commits"], 0)

    def test_repository_conflict_not_audited(self):
        self.state["repo_error"] = "CONFLICT_VERSION"
        self.assert_error("CONFLICT_VERSION")
        self.assertEqual(self.state["audits"], 0)
        self.assertEqual(self.state["completes"], 0)
        self.assertEqual(self.state["commits"], 0)

    def test_missing_replay_target_fails_closed(self):
        self.start()
        self.state["current"] = None
        self.assert_error("WORKFLOW_UNAVAILABLE")
        self.assertEqual(self.state["commits"], 1)

    def test_invalid_key_or_version_before_authentication(self):
        self.assert_error("VALIDATION_FAILED", key="too-short")
        self.assert_error("VALIDATION_FAILED", StartWorkflow(
            b"s" * 32, b"c" * 32, self.project_id, uuid.uuid4(), True))
        self.assertEqual(self.state["auth"], 0)


if __name__ == "__main__":
    unittest.main()
