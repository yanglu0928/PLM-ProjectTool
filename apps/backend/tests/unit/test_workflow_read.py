import uuid
import unittest
from dataclasses import replace
from types import SimpleNamespace

from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.workflow.application.read_workflow import (
    ChecklistView, StageView, WorkflowView, WorkflowReadError, WorkflowReadQuery, WorkflowReadService,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition


def snapshot():
    return WorkflowView(uuid.uuid4(), uuid.uuid4(), 1, "NOT_STARTED", None, tuple(
        StageView(s.stage_key, s.order, "NOT_STARTED", tuple(ChecklistView(i.item_key, i.required, "PENDING") for i in s.checklist_items))
        for s in six_stage_definition().stages
    ), 0)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class WorkflowReadTests(unittest.TestCase):
    def test_initial_projection_and_etag(self):
        view = snapshot()
        self.assertEqual(view.etag, '"v0"')
        self.assertEqual(sum(len(s.checklist_items) for s in view.stages), 12)

    def test_incomplete_definition_bad_state_and_version_rejected(self):
        view = snapshot()
        for changes in (
            dict(version=2), dict(version=True), dict(lock_version=-1), dict(lock_version=True),
            dict(stages=view.stages[:5]), dict(current_stage="HANDOVER"), dict(state="INVALID"),
            dict(stages=(replace(view.stages[0], checklist_items=()),)+view.stages[1:]),
            dict(stages=(replace(view.stages[0], state="ACTIVE"),)+view.stages[1:]),
        ):
            with self.subTest(changes=changes), self.assertRaises(WorkflowReadError): replace(view, **changes)

    def test_active_blocked_and_completed_pointer_consistency(self):
        view = snapshot()
        for state in ("ACTIVE", "BLOCKED"):
            stages = (replace(view.stages[0], state=state),)+view.stages[1:]
            active = replace(view, state="ACTIVE", current_stage="HANDOVER", stages=stages, lock_version=1)
            self.assertEqual(active.current_stage, "HANDOVER")
            with self.assertRaises(WorkflowReadError): replace(active, current_stage="SURVEY")
        completed = replace(view, state="COMPLETED", current_stage="PLAN", stages=tuple(replace(s, state="COMPLETED") for s in view.stages))
        with self.assertRaises(WorkflowReadError): replace(completed, current_stage=None)

    def test_same_transaction_authorization_and_repository_no_commit(self):
        view, actor = snapshot(), uuid.uuid4()
        seen = []
        def proof(tx, **kwargs):
            seen.append(tx)
            return AuthorizedProjectAction(actor, view.project_id, "WORKFLOW_GET", "CUSTOMER_MEMBER")
        def read(tx, project):
            self.assertIs(tx, seen[0])
            self.assertEqual(project, view.project_id)
            return view
        service = WorkflowReadService(unit_of_work=Tx,
            sessions=SimpleNamespace(authenticated_user=lambda *_args, **_kwargs: actor),
            projects=SimpleNamespace(require_in_transaction=proof),
            license_guard=SimpleNamespace(require_valid=lambda **_kwargs: None),
            repository=SimpleNamespace(get=read))
        self.assertIs(service.get(WorkflowReadQuery(b"s"*32, view.project_id, uuid.uuid4())), view)

    def test_missing_instance_and_foreign_projection_fail_closed(self):
        view, actor = snapshot(), uuid.uuid4()
        repository = SimpleNamespace(get=lambda *_args: None)
        service = WorkflowReadService(unit_of_work=Tx,
            sessions=SimpleNamespace(authenticated_user=lambda *_args, **_kwargs: actor),
            projects=SimpleNamespace(require_in_transaction=lambda *_args, **_kwargs: AuthorizedProjectAction(actor, view.project_id, "WORKFLOW_GET", "PROJECT_MANAGER")),
            license_guard=SimpleNamespace(require_valid=lambda **_kwargs: None), repository=repository)
        query = WorkflowReadQuery(b"s"*32, view.project_id, uuid.uuid4())
        with self.assertRaises(WorkflowReadError) as error: service.get(query)
        self.assertEqual(error.exception.code, "RESOURCE_NOT_FOUND")
        repository.get = lambda *_args: replace(view, project_id=uuid.uuid4())
        with self.assertRaises(WorkflowReadError) as error: service.get(query)
        self.assertEqual(error.exception.code, "WORKFLOW_UNAVAILABLE")
