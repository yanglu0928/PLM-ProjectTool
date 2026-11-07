"""Atomic, fail-closed PENDING -> RUNNING PluginExecution transition."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

_WORKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", re.ASCII)


class PluginExecutionStartError(RuntimeError):
    """Fixed, non-sensitive rejection for a start transition."""

    def __init__(self) -> None:
        self.code = "PLUGIN_EXECUTION_NOT_STARTABLE"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class StartPluginExecutionCommand:
    claim: ClaimedJob
    worker_ref: str


@dataclass(frozen=True, slots=True)
class PluginExecutionStartFacts:
    plugin_execution_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    attempt_no: int
    execution_state: str
    lock_version: int
    changed: bool


@dataclass(frozen=True, slots=True)
class PluginExecutionStartResult:
    plugin_execution_id: uuid.UUID
    execution_state: str
    changed: bool


class PluginExecutionStartJobsPort(Protocol):
    def check_output_claim_in_transaction(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> ClaimedJob: ...


class PluginExecutionStartRepositoryPort(Protocol):
    def lock_execution(
        self, transaction: object, *, claim: ClaimedJob,
    ) -> PluginExecutionStartFacts: ...
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def start_execution(
        self, transaction: object, *, claim: ClaimedJob,
        plugin_execution_id: uuid.UUID, expected_lock_version: int,
    ) -> PluginExecutionStartFacts: ...
    def append_state_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, from_state: str, to_state: str,
        trace_id: uuid.UUID,
    ) -> None: ...


class PluginExecutionStartOwner:
    """Verifies a current Job fence before starting the persistent execution state."""

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        jobs: PluginExecutionStartJobsPort,
        repository: PluginExecutionStartRepositoryPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (unit_of_work, jobs, repository, audit)):
            raise ValueError("PluginExecution start dependencies are required")
        self._uow = unit_of_work
        self._jobs = jobs
        self._repository = repository
        self._audit = audit

    def start(self, command: StartPluginExecutionCommand) -> PluginExecutionStartResult:
        self._validate(command)
        claim = command.claim
        trace_id = self._trace_uuid(claim.trace_id)
        try:
            with self._uow() as transaction:
                current = self._jobs.check_output_claim_in_transaction(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token,
                    worker_ref=command.worker_ref,
                )
                if type(current) is not ClaimedJob or current != claim:
                    raise PluginExecutionStartError()

                candidate = self._repository.lock_execution(
                    transaction, claim=current,
                )
                if (type(candidate) is not PluginExecutionStartFacts
                        or candidate.project_id != claim.project_id
                        or candidate.job_id != claim.job_id
                        or candidate.attempt_no != claim.attempt_no
                        or type(candidate.plugin_execution_id) is not uuid.UUID
                        or not candidate.plugin_execution_id.int
                        or type(candidate.lock_version) is not int
                        or candidate.lock_version < 0):
                    raise PluginExecutionStartError()

                if candidate.execution_state == "RUNNING":
                    if candidate.changed:
                        raise PluginExecutionStartError()
                    transaction.commit()
                    return PluginExecutionStartResult(
                        candidate.plugin_execution_id, "RUNNING", False,
                    )
                if candidate.execution_state != "PENDING" or candidate.changed:
                    raise PluginExecutionStartError()

                self._repository.authorize_owner_writes(transaction)
                started = self._repository.start_execution(
                    transaction, claim=current,
                    plugin_execution_id=candidate.plugin_execution_id,
                    expected_lock_version=candidate.lock_version,
                )
                if (type(started) is not PluginExecutionStartFacts
                        or started.plugin_execution_id != candidate.plugin_execution_id
                        or started.project_id != claim.project_id
                        or started.job_id != claim.job_id
                        or started.attempt_no != claim.attempt_no
                        or started.execution_state != "RUNNING"
                        or started.lock_version != candidate.lock_version + 1
                        or not started.changed):
                    raise PluginExecutionStartError()

                self._repository.append_state_event(
                    transaction, plugin_execution_id=started.plugin_execution_id,
                    project_id=started.project_id, from_state="PENDING",
                    to_state="RUNNING", trace_id=trace_id,
                )
                self._audit.append(
                    transaction,
                    AuditEventDraft(
                        trace_id=trace_id,
                        event_scope="PROJECT",
                        target_project_id=started.project_id,
                        actor_type="UNRESOLVED",
                        actor_id=None,
                        original_actor_id=None,
                        actor_hint_digest=None,
                        action="PLUGIN_EXECUTION_STARTED",
                        outcome="SUCCESS",
                        target_owner_module="plugin",
                        target_object_type="PLG-03",
                        target_object_id=started.plugin_execution_id,
                        before_state="PENDING",
                        after_state="RUNNING",
                    ),
                )
                transaction.commit()
                return PluginExecutionStartResult(
                    started.plugin_execution_id, "RUNNING", True,
                )
        except PluginExecutionStartError:
            raise
        except JobLeaseError:
            raise PluginExecutionStartError() from None
        except Exception:
            raise PluginExecutionStartError() from None

    @staticmethod
    def _validate(command: object) -> None:
        if (type(command) is not StartPluginExecutionCommand
                or type(command.claim) is not ClaimedJob
                or type(command.worker_ref) is not str
                or _WORKER.fullmatch(command.worker_ref) is None):
            raise PluginExecutionStartError()
        claim = command.claim
        if (claim.job_type != "OUTPUT_GENERATE" or claim.scope != "PROJECT"
                or type(claim.project_id) is not uuid.UUID or not claim.project_id.int
                or type(claim.fencing_token) is not int or claim.fencing_token < 1
                or type(claim.attempt_no) is not int or claim.attempt_no != 1):
            raise PluginExecutionStartError()

    @staticmethod
    def _trace_uuid(value: object) -> uuid.UUID:
        try:
            parsed = uuid.UUID(value)
        except (TypeError, ValueError, AttributeError):
            raise PluginExecutionStartError() from None
        if str(parsed) != value:
            raise PluginExecutionStartError()
        return parsed
