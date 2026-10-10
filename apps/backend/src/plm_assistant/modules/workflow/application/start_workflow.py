"""Authorized, audited and idempotent activation of the fixed first Workflow stage."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)
from plm_assistant.modules.workflow.application.read_workflow import (
    ChecklistView, StageView, WorkflowView,
)
from plm_assistant.modules.workflow.application.start_errors import WorkflowStartRepositoryError
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition


class WorkflowStartError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StartWorkflow:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    project_id: uuid.UUID
    trace_id: uuid.UUID
    expected_version: int


class SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class ProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class StartRepositoryPort(Protocol):
    def start(self, transaction: object, *, project_id: uuid.UUID,
              expected_version: int) -> WorkflowView: ...


class ReadRepositoryPort(Protocol):
    def get(self, transaction: object, project_id: uuid.UUID) -> WorkflowView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def _first_result(current: WorkflowView, project_id: uuid.UUID, workflow_id: uuid.UUID) -> WorkflowView:
    """Recover the immutable V1 start response, never today's Workflow state."""
    if (type(current) is not WorkflowView or current.project_id != project_id
            or current.workflow_id != workflow_id or current.version != 1
            or current.state not in ("ACTIVE", "COMPLETED") or current.lock_version < 1):
        raise WorkflowStartError("WORKFLOW_UNAVAILABLE")
    definition = six_stage_definition(1)
    stages = tuple(StageView(stage.stage_key, stage.order,
                             "ACTIVE" if index == 0 else "NOT_STARTED",
                             tuple(ChecklistView(item.item_key, item.required, "PENDING")
                                   for item in stage.checklist_items))
                   for index, stage in enumerate(definition.stages))
    first = WorkflowView(workflow_id, project_id, 1, "ACTIVE",
                         definition.stages[0].stage_key, stages, 1)
    first.__post_init__()
    return first


class WorkflowStartService:
    def __init__(self, *, unit_of_work: Callable[[], object], sessions: SessionPort,
                 projects: ProjectPort, license_guard: LicensePort,
                 starter: StartRepositoryPort, reader: ReadRepositoryPort,
                 receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, sessions, projects,
                                           license_guard, starter, reader, receipts, audit)):
            raise ValueError("Current Workflow start dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._starter, self._reader = license_guard, starter, reader
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start(self, command: StartWorkflow, *, idempotency_key: str) -> WorkflowView:
        if (type(command) is not StartWorkflow
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (command.project_id, command.trace_id))
                or type(command.expected_version) is not int
                or not 0 <= command.expected_version < 2**63):
            raise WorkflowStartError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "expected_version": command.expected_version,
            })
            # Authenticate before exposing License state; actual write repeats the proof.
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                proof = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="WORKFLOW_START",
                )
                if (type(proof) is not AuthorizedProjectAction or proof.user_id != actor
                        or proof.project_id != command.project_id
                        or proof.operation != "WORKFLOW_START"
                        or proof.project_role != "PROJECT_MANAGER"):
                    raise WorkflowStartError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation="V1_WORKFLOW_START", key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (type(replay) is not IdempotencyResult
                            or replay.ref_type != "V1_WORKFLOW_START"
                            or replay.status_code != 200):
                        raise WorkflowStartError("WORKFLOW_UNAVAILABLE")
                    current = self._reader.get(tx, command.project_id)
                    return _first_result(current, command.project_id, replay.ref_id)

                first = self._starter.start(
                    tx, project_id=command.project_id,
                    expected_version=command.expected_version,
                )
                if (type(first) is not WorkflowView or first.project_id != command.project_id
                        or first.state != "ACTIVE" or first.current_stage != "HANDOVER"
                        or first.lock_version != 1):
                    raise WorkflowStartError("WORKFLOW_UNAVAILABLE")
                if first != _first_result(first, command.project_id, first.workflow_id):
                    raise WorkflowStartError("WORKFLOW_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="WORKFLOW_STARTED", outcome="SUCCESS",
                    target_owner_module="workflow", target_object_type="WFL-01",
                    target_object_id=first.workflow_id,
                    before_state="NOT_STARTED", after_state="ACTIVE",
                ))
                self._receipts.complete(tx, scope=scope,
                                        result=IdempotencyResult(
                                            "V1_WORKFLOW_START", first.workflow_id, 200))
                tx.commit()
                return first
        except WorkflowStartError:
            raise
        except WorkflowStartRepositoryError as error:
            raise WorkflowStartError(error.code) from None
        except IdempotencyError as error:
            raise WorkflowStartError(error.code) from None
        except ProjectAuthorizationError as error:
            raise WorkflowStartError(error.code) from None
        except RuntimeLicenseError:
            raise WorkflowStartError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise WorkflowStartError("WORKFLOW_UNAVAILABLE") from None

    def _actor(self, transaction: object, command: StartWorkflow) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise WorkflowStartError("WORKFLOW_UNAVAILABLE")
        actor = self._sessions.authenticated_user(
            transaction, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise WorkflowStartError("AUTH_ACCESS_DENIED")
        return actor
