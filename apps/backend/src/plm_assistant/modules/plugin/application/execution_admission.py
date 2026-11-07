"""Atomic, fail-closed creation of a first PluginExecution admission."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob,
    JobLeaseError,
)
from plm_assistant.modules.output.application.job_admission import (
    OutputExecutionAdmission,
    OutputJobAdmissionError,
)
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

_WORKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", re.ASCII)


class PluginExecutionAdmissionError(RuntimeError):
    """Fixed, non-sensitive rejection for execution admission."""

    def __init__(self, code: str = "PLUGIN_EXECUTION_NOT_ADMITTED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AdmitPluginExecutionCommand:
    claim: ClaimedJob
    worker_ref: str


@dataclass(frozen=True, slots=True)
class PluginExecutionTarget:
    """Stable Plugin-owned identity; deliberately contains no filesystem path."""

    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    plugin_id_normalized: str
    operation_id: str


@dataclass(frozen=True, slots=True)
class PluginExecutionAdmissionSnapshot:
    plugin_execution_id: uuid.UUID
    project_id: uuid.UUID
    output_request_id: uuid.UUID
    output_context_snapshot_id: uuid.UUID
    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    plugin_id_normalized: str
    operation_id: str
    context_fingerprint: bytes
    job_id: uuid.UUID
    attempt_no: int
    execution_state: str


@dataclass(frozen=True, slots=True)
class PluginExecutionAdmissionResult:
    plugin_execution_id: uuid.UUID
    execution_state: str
    created: bool


class PluginExecutionLeasePort(Protocol):
    def check_output_claim_in_transaction(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> ClaimedJob: ...


class PluginExecutionOutputAdmissionPort(Protocol):
    def admit_in_transaction(
        self, transaction: object, claim: ClaimedJob,
    ) -> OutputExecutionAdmission: ...


class PluginExecutionTargetReaderPort(Protocol):
    def get_execution_target(
        self, transaction: object, *, operation_id: str,
    ) -> PluginExecutionTarget | None: ...


class PluginExecutionAdmissionRepositoryPort(Protocol):
    def find_by_job(
        self, transaction: object, *, job_id: uuid.UUID,
    ) -> PluginExecutionAdmissionSnapshot | None: ...
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def create_pending(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        command: AdmitPluginExecutionCommand,
        admission: OutputExecutionAdmission, target: PluginExecutionTarget,
        trace_id: uuid.UUID, idempotency_key: str,
    ) -> PluginExecutionAdmissionSnapshot: ...
    def append_pending_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, trace_id: uuid.UUID,
    ) -> None: ...


class PluginExecutionAdmissionOwner:
    """Persist one initial PENDING attempt; this owner never runs a Plugin."""

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        jobs: PluginExecutionLeasePort,
        output_admission: PluginExecutionOutputAdmissionPort,
        targets: PluginExecutionTargetReaderPort,
        repository: PluginExecutionAdmissionRepositoryPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, jobs, output_admission, targets, repository, audit,
        )):
            raise ValueError("PluginExecution admission dependencies are required")
        self._uow = unit_of_work
        self._jobs = jobs
        self._output = output_admission
        self._targets = targets
        self._repository = repository
        self._audit = audit

    def admit(
        self, command: AdmitPluginExecutionCommand,
    ) -> PluginExecutionAdmissionResult:
        self._validate_command(command)
        claim = command.claim
        try:
            trace_id = self._trace_uuid(claim.trace_id)
            with self._uow() as transaction:
                current = self._jobs.check_output_claim_in_transaction(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token,
                    worker_ref=command.worker_ref,
                )
                if type(current) is not ClaimedJob or current != claim:
                    raise PluginExecutionAdmissionError()

                admission = self._output.admit_in_transaction(
                    transaction, current,
                )
                if (type(admission) is not OutputExecutionAdmission
                        or admission.job_id != current.job_id
                        or admission.project_id != current.project_id):
                    raise PluginExecutionAdmissionError()

                target = self._targets.get_execution_target(
                    transaction, operation_id=admission.plugin_operation,
                )
                if (type(target) is not PluginExecutionTarget
                        or target.operation_id != admission.plugin_operation
                        or type(target.plugin_installation_id) is not uuid.UUID
                        or not target.plugin_installation_id.int
                        or type(target.plugin_package_id) is not uuid.UUID
                        or not target.plugin_package_id.int
                        or type(target.plugin_id_normalized) is not str
                        or not target.plugin_id_normalized):
                    raise PluginExecutionAdmissionError()

                existing = self._repository.find_by_job(
                    transaction, job_id=current.job_id,
                )
                if existing is not None:
                    self._check_replay(existing, admission, target, current)
                    transaction.commit()
                    return PluginExecutionAdmissionResult(
                        existing.plugin_execution_id,
                        existing.execution_state,
                        False,
                    )

                execution_id = uuid.uuid4()
                idempotency_key = f"plugin-execution:{current.job_id}"
                self._repository.authorize_owner_writes(transaction)
                created = self._repository.create_pending(
                    transaction, plugin_execution_id=execution_id,
                    command=command, admission=admission, target=target,
                    trace_id=trace_id, idempotency_key=idempotency_key,
                )
                self._repository.append_pending_event(
                    transaction, plugin_execution_id=execution_id,
                    project_id=admission.project_id, trace_id=trace_id,
                )
                self._audit.append(
                    transaction,
                    AuditEventDraft(
                        trace_id=trace_id,
                        event_scope="PROJECT",
                        target_project_id=admission.project_id,
                        actor_type="UNRESOLVED",
                        actor_id=None,
                        original_actor_id=None,
                        actor_hint_digest=None,
                        action="PLUGIN_EXECUTION_ADMIT",
                        outcome="SUCCESS",
                        target_owner_module="plugin",
                        target_object_type="PLG-03",
                        target_object_id=execution_id,
                        after_state="PENDING",
                    ),
                )
                transaction.commit()
                return PluginExecutionAdmissionResult(
                    created.plugin_execution_id,
                    created.execution_state,
                    True,
                )
        except PluginExecutionAdmissionError:
            raise
        except (JobLeaseError, OutputJobAdmissionError):
            raise PluginExecutionAdmissionError() from None
        except Exception:
            # Infrastructure details and caller-provided values are never exposed.
            raise PluginExecutionAdmissionError() from None

    @staticmethod
    def _validate_command(command: object) -> None:
        if (type(command) is not AdmitPluginExecutionCommand
                or type(command.claim) is not ClaimedJob
                or type(command.worker_ref) is not str
                or _WORKER.fullmatch(command.worker_ref) is None):
            raise PluginExecutionAdmissionError()
        claim = command.claim
        if (claim.job_type != "OUTPUT_GENERATE"
                or claim.scope != "PROJECT"
                or type(claim.project_id) is not uuid.UUID
                or not claim.project_id.int
                or type(claim.fencing_token) is not int
                or claim.fencing_token < 1
                or type(claim.attempt_no) is not int
                or claim.attempt_no != 1):
            raise PluginExecutionAdmissionError()

    @staticmethod
    def _trace_uuid(value: object) -> uuid.UUID:
        try:
            parsed = uuid.UUID(value)
        except (TypeError, ValueError, AttributeError):
            raise PluginExecutionAdmissionError() from None
        if str(parsed) != value:
            raise PluginExecutionAdmissionError()
        return parsed

    @staticmethod
    def _check_replay(
        existing: PluginExecutionAdmissionSnapshot,
        admission: OutputExecutionAdmission,
        target: PluginExecutionTarget,
        claim: ClaimedJob,
    ) -> None:
        if (type(existing) is not PluginExecutionAdmissionSnapshot
                or existing.project_id != admission.project_id
                or existing.output_request_id != admission.output_request_id
                or existing.output_context_snapshot_id
                    != admission.context_snapshot_id
                or existing.plugin_installation_id
                    != target.plugin_installation_id
                or existing.plugin_package_id != target.plugin_package_id
                or existing.plugin_id_normalized != target.plugin_id_normalized
                or existing.operation_id != admission.plugin_operation
                or existing.context_fingerprint != admission.context_fingerprint
                or existing.job_id != claim.job_id
                or existing.attempt_no != claim.attempt_no):
            raise PluginExecutionAdmissionError("PLUGIN_EXECUTION_CONFLICT")
