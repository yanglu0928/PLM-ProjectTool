import uuid
import unittest

from plm_assistant.modules.workflow.application.initialize import (
    InitializedWorkflow, WorkflowInitializationService,
)


class Repository:
    def __init__(self):
        self.result = InitializedWorkflow(uuid.uuid4(), True)
        self.calls = []

    def initialize(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.result


class Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append((tx, event))


class WorkflowInitializeTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.audit = Repository(), Audit()
        self.service = WorkflowInitializationService(repository=self.repo, audit=self.audit)
        self.tx = object()
        self.kwargs = dict(project_id=uuid.uuid4(), actor_id=uuid.uuid4(), trace_id=uuid.uuid4())

    def test_same_transaction_fixed_definition_and_initial_audit(self):
        result = self.service.initialize_in_transaction(self.tx, **self.kwargs)
        self.assertEqual(result, self.repo.result.workflow_id)
        self.assertIs(self.repo.calls[0][0], self.tx)
        self.assertEqual(self.repo.calls[0][1]["definition"].version, 1)
        self.assertIs(self.audit.events[0][0], self.tx)
        event = self.audit.events[0][1]
        self.assertEqual(event.action, "WORKFLOW_INITIALIZED")
        self.assertEqual(event.after_state, "NOT_STARTED")
        self.assertEqual(event.target_project_id, self.kwargs["project_id"])

    def test_existing_workflow_not_reset_or_audited_again(self):
        self.repo.result = InitializedWorkflow(self.repo.result.workflow_id, False)
        self.assertEqual(self.service.initialize_in_transaction(self.tx, **self.kwargs), self.repo.result.workflow_id)
        self.assertEqual(self.audit.events, [])

    def test_identity_and_dependencies_fail_closed(self):
        for key in self.kwargs:
            for value in (None, str(uuid.uuid4()), uuid.UUID(int=0)):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.service.initialize_in_transaction(self.tx, **(self.kwargs | {key: value}))
        with self.assertRaises(ValueError):
            self.service.initialize_in_transaction(None, **self.kwargs)
        for repository, audit in ((None, self.audit), (self.repo, None)):
            with self.assertRaises(ValueError):
                WorkflowInitializationService(repository=repository, audit=audit)
        self.assertEqual(self.repo.calls, [])

    def test_bad_result_and_audit_failure_propagate(self):
        for result in (None, InitializedWorkflow(uuid.UUID(int=0), True), InitializedWorkflow(uuid.uuid4(), 1)):
            self.repo.result = result
            with self.assertRaises(RuntimeError):
                self.service.initialize_in_transaction(self.tx, **self.kwargs)
        self.repo.result = InitializedWorkflow(uuid.uuid4(), True)
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.service.initialize_in_transaction(self.tx, **self.kwargs)
