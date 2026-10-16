"""Atomically publish one schema-valid AI suggestion and successful job result."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentSourceIdentity,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
    PersistedAIExecutionContentPlan,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint

from .provider_response_parser import ParsedAISuggestion
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AITaskSuggestionPublicationError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_RESULT_NOT_PUBLISHED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AISuggestionEvidence:
    ordinal: int
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    content_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or not 1 <= self.ordinal <= 256
                or type(self.owner_module) is not str or not self.owner_module
                or type(self.object_type) is not str or not self.object_type
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    self.object_id, self.version_id))
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32):
            raise AITaskSuggestionPublicationError()


@dataclass(frozen=True, slots=True)
class PublishedAITaskSuggestion:
    suggestion_payload_id: uuid.UUID
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.suggestion_payload_id) is not uuid.UUID
                or not self.suggestion_payload_id.int
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise AITaskSuggestionPublicationError()


class AITaskSuggestionSuccessStorePort(Protocol):
    def publish(
        self, transaction: object, *, parsed: ParsedAISuggestion,
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        evidence: tuple[AISuggestionEvidence, ...],
    ) -> PublishedAITaskSuggestion: ...


class _JobFinisher(Protocol):
    def finish(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> ClaimedJob: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class AITaskSuggestionSuccessPublisher:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        plans: AIExecutionContentPlanOwner,
        store: AITaskSuggestionSuccessStorePort,
        jobs: _JobFinisher, audit: AuditService,
        system_actor: _SystemActor,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, plans, store, jobs, audit, system_actor)):
            raise ValueError("AI suggestion publication dependencies required")
        self._uow = unit_of_work
        self._plans = plans
        self._store = store
        self._jobs = jobs
        self._audit = audit
        self._actor = system_actor

    def publish(
        self, *, parsed: ParsedAISuggestion,
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        worker_ref: str,
    ) -> PublishedAITaskSuggestion:
        if (type(parsed) is not ParsedAISuggestion
                or type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(worker_ref) is not str or not worker_ref.strip()):
            raise AITaskSuggestionPublicationError()
        try:
            parsed.__post_init__()
            prepared.__post_init__()
            begun.__post_init__()
            self._require_identity(parsed, prepared, begun)
            validate_checkpoint(
                job_id=prepared.grant.job_id,
                fencing_token=prepared.grant.fencing_token,
                worker_ref=worker_ref,
            )
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise AITaskSuggestionPublicationError()
            grant = prepared.grant
            with self._uow() as transaction:
                finished = self._jobs.finish(
                    transaction, job_id=grant.job_id,
                    fencing_token=grant.fencing_token,
                    worker_ref=worker_ref,
                )
                self._require_finished(finished, prepared)
                persisted = self._plans.get(
                    transaction, content_plan_id=grant.content_plan_id,
                )
                evidence = self._resolve_evidence(
                    parsed, prepared, persisted,
                )
                result = self._store.publish(
                    transaction, parsed=parsed, prepared=prepared,
                    begun=begun, evidence=evidence,
                )
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=grant.trace_id,
                    event_scope="PROJECT",
                    target_project_id=grant.project_id,
                    actor_type="SYSTEM",
                    actor_id=actor_id,
                    original_actor_id=grant.requested_by,
                    actor_hint_digest=None,
                    action="AI_TASK_SUGGESTION_AVAILABLE",
                    outcome="SUCCESS",
                    target_owner_module="ai",
                    target_object_type="AI-04",
                    target_object_id=grant.ai_task_id,
                    target_version_id=result.suggestion_payload_id,
                    before_state="RUNNING",
                    after_state="AVAILABLE",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise AITaskSuggestionPublicationError()
                transaction.commit()
            return result
        except AITaskSuggestionPublicationError:
            raise
        except JobLeaseError:
            raise AITaskSuggestionPublicationError(
                "AI_TASK_JOB_LEASE_LOST",
            ) from None
        except Exception:
            raise AITaskSuggestionPublicationError() from None

    @staticmethod
    def _require_identity(
        parsed: ParsedAISuggestion, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation,
    ) -> None:
        grant = prepared.grant
        if (begun.grant != grant
                or parsed.ai_task_id != grant.ai_task_id
                or parsed.ai_invocation_id != begun.ai_invocation_id
                or parsed.project_id != grant.project_id
                or parsed.output_schema_ref != grant.output_schema_ref
                or parsed.schema_version != grant.schema_version):
            raise AITaskSuggestionPublicationError()

    @staticmethod
    def _require_finished(
        value: ClaimedJob, prepared: PreparedAITaskInvocation,
    ) -> None:
        grant = prepared.grant
        expected_payload = {
            "ai_task_id": str(grant.ai_task_id),
            "egress_authorization_ref": str(grant.authorization_ref),
            "input_fingerprint": grant.source_refs_fingerprint.hex(),
        }
        if (type(value) is not ClaimedJob
                or value.job_id != grant.job_id
                or value.job_type != "AI_TASK_EXECUTE"
                or value.scope != "PROJECT"
                or value.project_id != grant.project_id
                or value.payload_refs != expected_payload
                or value.trace_id != str(grant.trace_id)
                or value.fencing_token != grant.fencing_token
                or value.attempt_no != grant.attempt_no):
            raise AITaskSuggestionPublicationError()

    @staticmethod
    def _resolve_evidence(
        parsed: ParsedAISuggestion, prepared: PreparedAITaskInvocation,
        persisted: PersistedAIExecutionContentPlan | None,
    ) -> tuple[AISuggestionEvidence, ...]:
        grant = prepared.grant
        if (type(persisted) is not PersistedAIExecutionContentPlan
                or persisted.plan.content_plan_id != grant.content_plan_id
                or persisted.plan.project_id != grant.project_id
                or persisted.plan.prompt.output_schema_ref != grant.output_schema_ref
                or persisted.plan.prompt.schema_version != grant.schema_version
                or not hmac.compare_digest(
                    persisted.payload_fingerprint,
                    grant.approved_payload_fingerprint)):
            raise AITaskSuggestionPublicationError()
        sources: dict[int, AIExecutionContentSourceIdentity] = {
            source.ordinal: source for source in persisted.plan.sources
        }
        inputs = {item.ordinal: item for item in grant.input_refs}
        result: list[AISuggestionEvidence] = []
        for result_ordinal, source_ordinal in enumerate(
                parsed.evidence_ordinals, 1):
            source = sources.get(source_ordinal)
            input_ref = inputs.get(source_ordinal)
            if (source is None or input_ref is None
                    or source.project_id != grant.project_id
                    or (source.resource_type, source.owner_module,
                        source.object_type, source.object_id, source.version_id)
                    != (input_ref.resource_type, input_ref.owner_module,
                        input_ref.object_type, input_ref.object_id,
                        input_ref.version_id)):
                raise AITaskSuggestionPublicationError()
            result.append(AISuggestionEvidence(
                result_ordinal, source.owner_module, source.object_type,
                source.object_id, source.version_id,
                source.content_fingerprint,
            ))
        return tuple(result)
