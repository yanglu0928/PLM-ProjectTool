import uuid
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.workflow.application.initialize_existing import (
    ExistingWorkflowInitializationService, InitializeExistingWorkflow, WorkflowInitializationError,
)


class Tx:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.state.append("commit")


class ExistingInitializationTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.actor, self.workflow = uuid.uuid4(), uuid.uuid4()
        self.command = InitializeExistingWorkflow(b"s"*32, b"c"*32, uuid.uuid4(), uuid.uuid4())
        self.sessions = SimpleNamespace(authenticated_user=self.authenticate)
        self.projects = SimpleNamespace(require_in_transaction=self.authorize)
        self.guard = SimpleNamespace(require_valid=lambda **_: self.events.append("license"))
        self.initializer = SimpleNamespace(initialize_in_transaction=self.bootstrap)
        self.service = ExistingWorkflowInitializationService(
            unit_of_work=lambda: Tx(self.events), sessions=self.sessions, projects=self.projects,
            license_guard=self.guard, initializer=self.initializer,
        )
    def authenticate(self, tx, **kwargs):
        self.events.append("session")
        return self.actor
    def authorize(self, tx, **kwargs):
        self.proof_tx = tx
        self.events.append("project")
        return AuthorizedProjectAction(kwargs["user_id"], kwargs["project_id"], kwargs["operation"], "PROJECT_MANAGER")
    def bootstrap(self, tx, **kwargs):
        self.assertIs(tx, self.proof_tx)
        self.assertEqual(kwargs["actor_id"], self.actor)
        self.events.append("initialize")
        return self.workflow

    def test_current_proof_and_bootstrap_in_same_write_transaction(self):
        self.assertEqual(self.service.initialize(self.command), self.workflow)
        self.assertEqual(self.events, ["session", "license", "session", "project", "initialize", "commit"])
    def test_authentication_denial_never_calls_license_or_write(self):
        self.sessions.authenticated_user = lambda *_args, **_kwargs: None
        with self.assertRaises(WorkflowInitializationError): self.service.initialize(self.command)
        self.assertEqual(self.events, [])
    def test_invalid_command_denied_without_io(self):
        for command in (None, replace(self.command, csrf_token=b"bad"), replace(self.command, project_id=uuid.UUID(int=0))):
            with self.assertRaises(WorkflowInitializationError): self.service.initialize(command)
        self.assertEqual(self.events, [])
    def test_wrong_authorization_proof_not_used(self):
        self.projects.require_in_transaction = lambda *_args, **_kwargs: AuthorizedProjectAction(
            self.actor, uuid.uuid4(), "WORKFLOW_START", "PROJECT_MANAGER")
        with self.assertRaises(WorkflowInitializationError): self.service.initialize(self.command)
        self.assertNotIn("initialize", self.events)
        self.assertNotIn("commit", self.events)
    def test_session_revalidated_after_license_check(self):
        count = []
        def access(*_args, **_kwargs):
            count.append(1)
            return self.actor if len(count)==1 else None
        self.sessions.authenticated_user = access
        with self.assertRaises(WorkflowInitializationError): self.service.initialize(self.command)
        self.assertEqual(len(count), 2)
        self.assertNotIn("initialize", self.events)
