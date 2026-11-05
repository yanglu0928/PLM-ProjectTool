"""Atomically publish an already-staged OutputArtifact and finish its Job."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import OutputGenerationFailureOwner
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


class OutputGenerationCompletionError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_COMPLETION_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


_VALIDATION_CODES = ("FORMAT_CHECK", "STRUCTURE_CHECK", "HASH_CHECK", "CONTENT_CHECK")
_MIME_BY_KIND = {
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
}


@dataclass(frozen=True, slots=True)
class OutputValidationEvidence:
    code: str
    state: str
    evidence_fingerprint: bytes | None = None

    def __post_init__(self) -> None:
        if (self.code not in _VALIDATION_CODES or self.state != "PASSED"
                or (self.evidence_fingerprint is not None
                    and (type(self.evidence_fingerprint) is not bytes
                         or len(self.evidence_fingerprint) != 32))):
            raise OutputGenerationCompletionError("OUTPUT_VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class OutputArtifactPublication:
    artifact_id: uuid.UUID
    plugin_execution_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    file_object_id: uuid.UUID
    sha256: bytes
    size_bytes: int
    media_type: str
    validations: tuple[OutputValidationEvidence, ...]

    def __post_init__(self) -> None:
        ids = (self.artifact_id, self.plugin_execution_id, self.document_id,
               self.document_version_id, self.file_object_id)
        if (any(type(value) is not uuid.UUID or not value.int for value in ids)
                or type(self.sha256) is not bytes or len(self.sha256) != 32
                or type(self.size_bytes) is not int or not 0 <= self.size_bytes <= 134217728
                or type(self.media_type) is not str
                or type(self.validations) is not tuple):
            raise OutputGenerationCompletionError()
        codes = tuple(item.code for item in self.validations
                      if type(item) is OutputValidationEvidence)
        if (len(self.validations) != len(_VALIDATION_CODES)
                or len(codes) != len(_VALIDATION_CODES)
                or set(codes) != set(_VALIDATION_CODES)):
            raise OutputGenerationCompletionError("OUTPUT_VALIDATION_FAILED")
        hash_evidence = next(item for item in self.validations if item.code == "HASH_CHECK")
        if hash_evidence.evidence_fingerprint != self.sha256:
            raise OutputGenerationCompletionError("OUTPUT_VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class OutputGenerationCompletionFacts:
    artifact_id: uuid.UUID | None
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    context_snapshot_id: uuid.UUID
    requested_by: uuid.UUID
    execution_id: uuid.UUID
    output_type: str
    request_state: str
    artifact_state: str
    lock_version: int
    changed: bool


class OutputGenerationCompletionRepositoryPort(Protocol):
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationCompletionFacts: ...
    def complete_generation(self, transaction: object, *, claim: ClaimedJob,
                            execution_id: uuid.UUID, expected_lock_version: int,
                            publication: OutputArtifactPublication
                            ) -> OutputGenerationCompletionFacts: ...


class OutputGenerationCompletionJobsPort(Protocol):
    def check_output_claim(self, transaction: object, *, job_id: uuid.UUID,
                           fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def finish(self, transaction: object, *, job_id: uuid.UUID,
               fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class OutputGenerationCompletionOwner:
    """Commit Artifact, OutputRequest, Job lease and Audit as one transaction."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 jobs: OutputGenerationCompletionJobsPort,
                 repository: OutputGenerationCompletionRepositoryPort,
                 audit: AuditService, system_actor_id: uuid.UUID) -> None:
        if (unit_of_work is None or jobs is None or repository is None or audit is None
                or type(system_actor_id) is not uuid.UUID or not system_actor_id.int):
            raise ValueError("Output generation completion dependencies are required")
        self._uow, self._jobs, self._repo, self._audit = unit_of_work, jobs, repository, audit
        self._system_actor_id = system_actor_id

    def complete(self, claim: ClaimedJob, *, worker_ref: str,
                 publication: OutputArtifactPublication
                 ) -> OutputGenerationCompletionFacts:
        try:
            request_id, snapshot_id, trace_id = OutputGenerationFailureOwner._validate_claim(
                claim, worker_ref)
        except Exception:
            raise OutputGenerationCompletionError() from None
        if (type(publication) is not OutputArtifactPublication
                or publication.plugin_execution_id
                != uuid.uuid5(claim.job_id, "output-generation:" + str(claim.fencing_token))):
            raise OutputGenerationCompletionError()
        try:
            with self._uow() as transaction:
                candidate = self._repo.lock_candidate(
                    transaction, claim=claim, execution_id=publication.plugin_execution_id,
                )
                if (type(candidate) is not OutputGenerationCompletionFacts
                        or candidate.artifact_id is not None
                        or candidate.output_request_id != request_id
                        or candidate.context_snapshot_id != snapshot_id
                        or candidate.job_id != claim.job_id
                        or candidate.project_id != claim.project_id
                        or candidate.execution_id != publication.plugin_execution_id
                        or candidate.request_state != "GENERATING"
                        or candidate.artifact_state != "MISSING"
                        or candidate.changed or candidate.lock_version < 1):
                    raise OutputGenerationCompletionError()
                current = self._jobs.check_output_claim(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token, worker_ref=worker_ref,
                )
                if (type(current) is not ClaimedJob or current != claim
                        or current.job_type != "OUTPUT_GENERATE"
                        or current.project_id != claim.project_id
                        or current.payload_refs != claim.payload_refs):
                    raise OutputGenerationCompletionError()
                facts = self._repo.complete_generation(
                    transaction, claim=claim, execution_id=publication.plugin_execution_id,
                    expected_lock_version=candidate.lock_version, publication=publication,
                )
                if (type(facts) is not OutputGenerationCompletionFacts
                        or facts.artifact_id != publication.artifact_id
                        or facts.output_request_id != request_id
                        or facts.context_snapshot_id != snapshot_id
                        or facts.job_id != claim.job_id or facts.project_id != claim.project_id
                        or facts.execution_id != publication.plugin_execution_id
                        or facts.request_state != "SUCCEEDED" or facts.artifact_state != "AVAILABLE"
                        or facts.lock_version != candidate.lock_version + 1 or not facts.changed):
                    raise OutputGenerationCompletionError()
                finished = self._jobs.finish(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token, worker_ref=worker_ref,
                )
                if type(finished) is not ClaimedJob or finished != claim:
                    raise OutputGenerationCompletionError()
                self._audit.append(transaction, AuditEventDraft(
                    trace_id=trace_id, event_scope="PROJECT",
                    target_project_id=facts.project_id, actor_type="SYSTEM",
                    actor_id=self._system_actor_id, original_actor_id=facts.requested_by,
                    actor_hint_digest=None, action="OUTPUT_GENERATION_SUCCEEDED",
                    outcome="SUCCESS", target_owner_module="output",
                    target_object_type="OUT-01", target_object_id=facts.output_request_id,
                    before_state="GENERATING", after_state="SUCCEEDED",
                ))
                transaction.commit()
                return facts
        except OutputGenerationCompletionError:
            raise
        except (JobLeaseError, IdempotencyError):
            raise OutputGenerationCompletionError() from None
        except Exception:
            raise OutputGenerationCompletionError("SYSTEM_UNAVAILABLE") from None
