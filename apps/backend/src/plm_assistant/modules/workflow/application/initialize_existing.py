"""Authorized internal initialization only; not the WORKFLOW_START HTTP command."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class WorkflowInitializationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InitializeExistingWorkflow:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    project_id: uuid.UUID
    trace_id: uuid.UUID


class WorkflowWriteSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class WorkflowProjectAuthorizationPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class WorkflowLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class WorkflowBootstrapPort(Protocol):
    def initialize_in_transaction(self, transaction: object, *, project_id: uuid.UUID,
                                  actor_id: uuid.UUID, trace_id: uuid.UUID) -> uuid.UUID: ...


class ExistingWorkflowInitializationService:
    """Explicit PM operation. Never bulk-backfills or starts inferred progress."""
    def __init__(self, *, unit_of_work: Callable[[], object],
                 sessions: WorkflowWriteSessionPort, projects: WorkflowProjectAuthorizationPort,
                 license_guard: WorkflowLicensePort, initializer: WorkflowBootstrapPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, sessions, projects, license_guard, initializer)):
            raise ValueError("authorized Workflow initialization dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._initializer = license_guard, initializer
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize(self, command: InitializeExistingWorkflow) -> uuid.UUID:
        if (type(command) is not InitializeExistingWorkflow
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (command.project_id, command.trace_id))):
            raise WorkflowInitializationError("VALIDATION_FAILED")
        # Authenticate before License evaluation; then revalidate current Session
        # and locked project facts in the actual write transaction.
        with self._uow() as tx:
            self._actor(tx, command)
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            actor = self._actor(tx, command)
            proof = self._projects.require_in_transaction(
                tx, user_id=actor, project_id=command.project_id, operation="WORKFLOW_START",
            )
            if (type(proof) is not AuthorizedProjectAction or proof.user_id != actor
                    or proof.project_id != command.project_id or proof.operation != "WORKFLOW_START"
                    or proof.project_role != "PROJECT_MANAGER"):
                raise WorkflowInitializationError("RESOURCE_NOT_FOUND")
            workflow_id = self._initializer.initialize_in_transaction(
                tx, project_id=command.project_id, actor_id=actor, trace_id=command.trace_id,
            )
            if type(workflow_id) is not uuid.UUID or workflow_id.int == 0:
                raise WorkflowInitializationError("WORKFLOW_UNAVAILABLE")
            tx.commit()
            return workflow_id

    def _actor(self, transaction: object, command: InitializeExistingWorkflow) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise WorkflowInitializationError("WORKFLOW_UNAVAILABLE")
        actor = self._sessions.authenticated_user(
            transaction, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise WorkflowInitializationError("AUTH_ACCESS_DENIED")
        return actor
