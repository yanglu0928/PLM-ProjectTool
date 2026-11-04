"""Fail-closed admission facts for a future Output execution consumer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.resolve_context import (
    PluginOperationCapability,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)


class OutputJobAdmissionError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_JOB_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutputJobAdmissionFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    context_snapshot_id: uuid.UUID
    request_state: str
    output_type: str
    template_version_ref: uuid.UUID
    source_version_refs: tuple[uuid.UUID, ...]
    output_policy_ref: str
    plugin_operation: str
    context_payload: dict = field(repr=False)
    context_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class OutputExecutionAdmission:
    """Minimal request facts; deliberately contains no snapshot body or file path."""

    output_request_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    context_snapshot_id: uuid.UUID
    output_type: str
    template_version_ref: uuid.UUID
    source_version_refs: tuple[uuid.UUID, ...]
    output_policy_ref: str
    plugin_operation: str
    context_fingerprint: bytes = field(repr=False)


class OutputJobAdmissionRepositoryPort(Protocol):
    def load(self, transaction: object, *, project_id: uuid.UUID,
             output_request_id: uuid.UUID, job_id: uuid.UUID,
             context_snapshot_id: uuid.UUID) -> OutputJobAdmissionFacts | None: ...


class OutputJobPluginCapabilityPort(Protocol):
    def get_operation(self, transaction: object, *,
                      operation_id: str) -> PluginOperationCapability | None: ...


class OutputJobExecutionAdmissionOwner:
    """Checks request/snapshot binding and current Plugin capability; executes nothing."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: OutputJobAdmissionRepositoryPort,
                 plugin_capabilities: OutputJobPluginCapabilityPort) -> None:
        if any(value is None for value in
               (unit_of_work, repository, plugin_capabilities)):
            raise ValueError("Output admission dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._plugin_capabilities = plugin_capabilities

    def admit(self, claim: ClaimedJob) -> OutputExecutionAdmission:
        request_id, snapshot_id = self._validate_claim(claim)
        if claim.job_type != "OUTPUT_GENERATE" or claim.scope != "PROJECT":
            raise OutputJobAdmissionError()
        try:
            with self._unit_of_work() as transaction:
                facts = self._repository.load(
                    transaction, project_id=claim.project_id,
                    output_request_id=request_id, job_id=claim.job_id,
                    context_snapshot_id=snapshot_id,
                )
                if type(facts) is not OutputJobAdmissionFacts:
                    raise OutputJobAdmissionError()
                self._validate_facts(facts, claim, request_id, snapshot_id)
                capability = self._plugin_capabilities.get_operation(
                    transaction, operation_id=facts.plugin_operation,
                )
                if (type(capability) is not PluginOperationCapability
                        or capability.operation_id != facts.plugin_operation
                        or capability.enabled is not True
                        or capability.trusted is not True
                        or type(capability.output_types) is not tuple
                        or facts.output_type not in capability.output_types):
                    raise OutputJobAdmissionError()
                return OutputExecutionAdmission(
                    output_request_id=facts.output_request_id,
                    project_id=facts.project_id,
                    job_id=facts.job_id,
                    context_snapshot_id=facts.context_snapshot_id,
                    output_type=facts.output_type,
                    template_version_ref=facts.template_version_ref,
                    source_version_refs=facts.source_version_refs,
                    output_policy_ref=facts.output_policy_ref,
                    plugin_operation=facts.plugin_operation,
                    context_fingerprint=facts.context_fingerprint,
                )
        except OutputJobAdmissionError:
            raise
        except Exception:
            # The admission boundary never converts unavailable facts into permission.
            raise OutputJobAdmissionError() from None

    @staticmethod
    def _validate_claim(claim: ClaimedJob) -> tuple[uuid.UUID, uuid.UUID]:
        if (type(claim) is not ClaimedJob
                or type(claim.job_id) is not uuid.UUID or not claim.job_id.int
                or type(claim.project_id) is not uuid.UUID or not claim.project_id.int
                or type(claim.job_type) is not str
                or type(claim.scope) is not str
                or type(claim.payload_refs) is not dict
                or set(claim.payload_refs) != {
                    "output_request_id", "context_snapshot_id",
                }
                or type(claim.fencing_token) is not int or claim.fencing_token < 1
                or type(claim.attempt_no) is not int or claim.attempt_no < 1):
            raise OutputJobAdmissionError()
        try:
            request_id = uuid.UUID(claim.payload_refs["output_request_id"])
            snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        except (TypeError, ValueError, AttributeError):
            raise OutputJobAdmissionError() from None
        if (not request_id.int or not snapshot_id.int
                or str(request_id) != claim.payload_refs["output_request_id"]
                or str(snapshot_id) != claim.payload_refs["context_snapshot_id"]):
            raise OutputJobAdmissionError()
        return request_id, snapshot_id

    @staticmethod
    def _validate_facts(facts: OutputJobAdmissionFacts, claim: ClaimedJob,
                        request_id: uuid.UUID, snapshot_id: uuid.UUID) -> None:
        if (facts.output_request_id != request_id
                or facts.project_id != claim.project_id
                or facts.job_id != claim.job_id
                or facts.context_snapshot_id != snapshot_id
                or facts.request_state != "QUEUED"
                or facts.output_type not in {"DOCX", "PPTX", "PNG", "JPEG"}
                or type(facts.template_version_ref) is not uuid.UUID
                or not facts.template_version_ref.int
                or type(facts.source_version_refs) is not tuple
                or not facts.source_version_refs
                or len(set(facts.source_version_refs)) != len(facts.source_version_refs)
                or any(type(value) is not uuid.UUID or not value.int
                       for value in facts.source_version_refs)
                or type(facts.output_policy_ref) is not str
                or not facts.output_policy_ref.strip()
                or type(facts.plugin_operation) is not str
                or not facts.plugin_operation.strip()
                or type(facts.context_payload) is not dict
                or type(facts.context_fingerprint) is not bytes
                or len(facts.context_fingerprint) != 32):
            raise OutputJobAdmissionError()
        try:
            if canonical_payload_fingerprint(facts.context_payload) != facts.context_fingerprint:
                raise OutputJobAdmissionError()
        except IdempotencyError:
            raise OutputJobAdmissionError() from None
