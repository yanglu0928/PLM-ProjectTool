"""Authorized, audited and idempotent Handover Stage Transition command."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification,
    HandoverWorkflowQualificationError,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowCurrentQualificationQuery,
    HandoverWorkflowQualificationOwnerError,
)
from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)

from .append_stage_transition import (
    AppendStageTransition, PersistedStageTransition,
    StageTransitionAppendError, TransitionGateProof,
)
from .current_checklist_record import ChecklistBasisObservation


_OPERATION = "V1_WORKFLOW_TRANSITION"
_ITEMS = ("HANDOVER_BASELINE", "HANDOVER_ISSUES")


class WorkflowStageTransitionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TransitionWorkflowStage:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    target_stage_key: str
    expected_workflow_version: int
    reason: str


class TransitionSessionPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class TransitionProjectPort(Protocol):
    def require_in_transaction(
        self, transaction: object, *, user_id: uuid.UUID,
        project_id: uuid.UUID, operation: str,
    ) -> AuthorizedProjectAction: ...


class TransitionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class TransitionQualificationPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: HandoverWorkflowCurrentQualificationQuery,
    ) -> HandoverChecklistQualification: ...


class TransitionRepositoryPort(Protocol):
    def append(
        self, transaction: object, *, command: AppendStageTransition,
    ) -> PersistedStageTransition: ...

    def get_transition(
        self, transaction: object, *, project_id: uuid.UUID,
        stage_transition_id: uuid.UUID,
    ) -> PersistedStageTransition | None: ...


class TransitionReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class WorkflowStageTransitionService:
    """Only HANDOVER -> SURVEY is registered until later Owners exist."""

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        sessions: TransitionSessionPort, projects: TransitionProjectPort,
        license_guard: TransitionLicensePort,
        qualification: TransitionQualificationPort,
        transitions: TransitionRepositoryPort,
        receipts: TransitionReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, sessions, projects, license_guard,
                qualification, transitions, receipts, audit)):
            raise ValueError("Workflow Stage Transition dependencies required")
        self._uow, self._sessions, self._projects = (
            unit_of_work, sessions, projects,
        )
        self._guard, self._qualification = license_guard, qualification
        self._transitions, self._receipts = transitions, receipts
        self._audit, self._clock = (
            audit, clock or (lambda: datetime.now(timezone.utc)),
        )

    def transition(
        self, command: TransitionWorkflowStage, *, idempotency_key: str,
    ) -> PersistedStageTransition:
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "target_stage_key": command.target_stage_key,
                "expected_workflow_version": (
                    command.expected_workflow_version
                ),
                "reason": command.reason,
            })
            # Authenticate before exposing License state; repeat inside write UOW.
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                proof = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="WORKFLOW_TRANSITION",
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor
                        or proof.project_id != command.project_id
                        or proof.operation != "WORKFLOW_TRANSITION"
                        or proof.project_role != "PROJECT_MANAGER"):
                    raise WorkflowStageTransitionError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope,
                    request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    return self._recover(tx, command, replay)

                qualifications = tuple(
                    self._qualify(tx, command, item_key)
                    for item_key in _ITEMS
                )
                self._same_handover(qualifications, command.project_id)
                gates = tuple(self._gate(value) for value in qualifications)
                occurred_at = self._now()
                result = self._transitions.append(
                    tx, command=AppendStageTransition(
                        command.project_id, command.target_stage_key,
                        command.expected_workflow_version, actor,
                        command.trace_id, command.reason, occurred_at, gates,
                    ),
                )
                if (type(result) is not PersistedStageTransition
                        or result.snapshot.project_id != command.project_id
                        or result.snapshot.actor_id != actor
                        or result.snapshot.trace_id != command.trace_id
                        or result.snapshot.from_stage != "HANDOVER"
                        or result.snapshot.to_stage
                           != command.target_stage_key
                        or result.snapshot.before_lock_version
                           != command.expected_workflow_version):
                    raise WorkflowStageTransitionError(
                        "WORKFLOW_UNAVAILABLE",
                    )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="WORKFLOW_STAGE_TRANSITIONED",
                    outcome="SUCCESS", target_owner_module="workflow",
                    target_object_type="WFL-02",
                    target_object_id=result.snapshot.workflow_id,
                    target_version_id=result.stage_transition_id,
                    before_state=result.snapshot.from_stage,
                    after_state=result.snapshot.to_stage,
                ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(
                        _OPERATION, result.stage_transition_id, 200,
                    ),
                )
                tx.commit()
                return result
        except WorkflowStageTransitionError:
            raise
        except StageTransitionAppendError as error:
            raise WorkflowStageTransitionError(error.code) from None
        except (HandoverWorkflowQualificationError,
                HandoverWorkflowQualificationOwnerError):
            raise WorkflowStageTransitionError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            ) from None
        except ProjectAuthorizationError as error:
            raise WorkflowStageTransitionError(error.code) from None
        except RuntimeLicenseError:
            raise WorkflowStageTransitionError(
                "LICENSE_OPERATION_DENIED",
            ) from None
        except IdempotencyError as error:
            raise WorkflowStageTransitionError(error.code) from None
        except Exception:
            raise WorkflowStageTransitionError(
                "WORKFLOW_UNAVAILABLE",
            ) from None

    def _qualify(
        self, tx: object, command: TransitionWorkflowStage, item_key: str,
    ) -> HandoverChecklistQualification:
        result = self._qualification.qualify_only_current_in_transaction(
            tx, HandoverWorkflowCurrentQualificationQuery(
                command.session_token, command.trace_id,
                command.project_id, item_key,
            ),
        )
        if type(result) is HandoverChecklistQualification:
            result.__post_init__()
        if (type(result) is not HandoverChecklistQualification
                or result.project_id != command.project_id
                or result.item_key != item_key):
            raise WorkflowStageTransitionError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        return result

    @staticmethod
    def _same_handover(
        values: tuple[HandoverChecklistQualification, ...],
        project_id: uuid.UUID,
    ) -> None:
        if (len(values) != len(_ITEMS)
                or tuple(value.item_key for value in values) != _ITEMS
                or any(value.project_id != project_id for value in values)
                or len({value.handover_analysis_version_id
                        for value in values}) != 1
                or len({value.review.review_id for value in values}) != 1
                or len({value.review.review_round_id for value in values}) != 1
                or len({value.review.subject_id for value in values}) != 1
                or len({value.review.subject_fingerprint
                        for value in values}) != 1):
            raise WorkflowStageTransitionError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )

    @staticmethod
    def _gate(
        value: HandoverChecklistQualification,
    ) -> TransitionGateProof:
        basis = [ChecklistBasisObservation(
            "EVIDENCE", observation.evidence_id, "PROJECT",
            observation.project_id, "ELIGIBLE",
            observation.observed_lock_version,
            observation.content_fingerprint,
            observation.verified_at, 1,
        ) for observation in value.evidence]
        basis.append(ChecklistBasisObservation(
            "REVIEW_ROUND", value.review.review_round_id, "PROJECT",
            value.review.project_id, "APPROVED",
            value.review.observed_lock_version,
            value.content_fingerprint, value.review.verified_at, 1,
        ))
        return TransitionGateProof(value.item_key, tuple(sorted(
            basis, key=lambda observation: (
                observation.ref_kind, str(observation.ref_id),
            ),
        )))

    def _recover(
        self, tx: object, command: TransitionWorkflowStage,
        receipt: IdempotencyResult,
    ) -> PersistedStageTransition:
        if (type(receipt) is not IdempotencyResult
                or receipt.ref_type != _OPERATION
                or receipt.status_code != 200):
            raise WorkflowStageTransitionError("WORKFLOW_UNAVAILABLE")
        result = self._transitions.get_transition(
            tx, project_id=command.project_id,
            stage_transition_id=receipt.ref_id,
        )
        if (type(result) is not PersistedStageTransition
                or result.snapshot.project_id != command.project_id
                or result.snapshot.to_stage != command.target_stage_key
                or result.snapshot.before_lock_version
                   != command.expected_workflow_version):
            raise WorkflowStageTransitionError("WORKFLOW_UNAVAILABLE")
        return result

    @staticmethod
    def _validate(command: TransitionWorkflowStage) -> None:
        if (type(command) is not TransitionWorkflowStage
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (command.trace_id, command.project_id))
                or command.target_stage_key != "SURVEY"
                or type(command.expected_workflow_version) is not int
                or not 0 <= command.expected_workflow_version < 2**63 - 1
                or type(command.reason) is not str
                or not 0 < len(command.reason) <= 2000
                or not command.reason.strip()
                or "\x00" in command.reason):
            raise WorkflowStageTransitionError("VALIDATION_FAILED")

    def _actor(
        self, tx: object, command: TransitionWorkflowStage,
    ) -> uuid.UUID:
        actor = self._sessions.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=self._now(),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise WorkflowStageTransitionError("AUTH_ACCESS_DENIED")
        return actor

    def _now(self) -> datetime:
        value = self._clock()
        if (type(value) is not datetime or value.tzinfo is None
                or value.utcoffset() is None):
            raise WorkflowStageTransitionError("WORKFLOW_UNAVAILABLE")
        return value.astimezone(timezone.utc)
