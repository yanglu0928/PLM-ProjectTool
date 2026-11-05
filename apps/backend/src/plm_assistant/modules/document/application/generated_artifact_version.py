"""System-owned immutable DocumentVersion creation for a completed Output execution.

This owner records database facts only. Storage promotion is handled by P34B.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import OutputGenerationFailureOwner
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


class GeneratedVersionError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_VERSION_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


_MEDIA = {
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
}


@dataclass(frozen=True, slots=True)
class GeneratedDocumentVersion:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    file_object_id: uuid.UUID
    plugin_execution_id: uuid.UUID
    sha256: bytes
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        ids = (self.document_id, self.document_version_id, self.file_object_id,
               self.plugin_execution_id)
        if (any(type(value) is not uuid.UUID or not value.int for value in ids)
                or type(self.sha256) is not bytes or len(self.sha256) != 32
                or type(self.size_bytes) is not int
                or not 0 <= self.size_bytes <= 134217728
                or type(self.media_type) is not str):
            raise GeneratedVersionError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class GeneratedVersionFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    file_object_id: uuid.UUID
    plugin_execution_id: uuid.UUID
    version_no: int
    changed: bool


class GeneratedVersionJobsPort(Protocol):
    def check_output_claim(self, transaction: object, *, job_id: uuid.UUID,
                           fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class GeneratedVersionRepositoryPort(Protocol):
    def lock_request(self, transaction: object, *, claim: ClaimedJob,
                     execution_id: uuid.UUID, publication: GeneratedDocumentVersion) -> bool: ...

    def commit_generated_version(
        self, transaction: object, *, claim: ClaimedJob, execution_id: uuid.UUID,
        system_actor_id: uuid.UUID, publication: GeneratedDocumentVersion,
    ) -> GeneratedVersionFacts: ...


class OutputGeneratedDocumentVersionOwner:
    """Create the immutable generated DocumentVersion under the current Job fence."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 jobs: GeneratedVersionJobsPort,
                 repository: GeneratedVersionRepositoryPort,
                 audit: AuditService, system_actor_id: uuid.UUID) -> None:
        if (unit_of_work is None or jobs is None or repository is None or audit is None
                or type(system_actor_id) is not uuid.UUID or not system_actor_id.int):
            raise ValueError("generated document version dependencies are required")
        self._uow, self._jobs, self._repository = unit_of_work, jobs, repository
        self._audit, self._system_actor_id = audit, system_actor_id

    def commit(self, claim: ClaimedJob, *, worker_ref: str,
               publication: GeneratedDocumentVersion) -> GeneratedVersionFacts:
        try:
            request_id, _, trace_id = OutputGenerationFailureOwner._validate_claim(
                claim, worker_ref)
        except Exception:
            raise GeneratedVersionError() from None
        expected_execution = uuid.uuid5(
            claim.job_id, "output-generation:" + str(claim.fencing_token))
        expected_version = uuid.uuid5(
            expected_execution, "generated-document-version:" + str(publication.file_object_id))
        if (type(publication) is not GeneratedDocumentVersion
                or claim.job_type != "OUTPUT_GENERATE" or claim.scope != "PROJECT"
                or publication.plugin_execution_id != expected_execution
                or publication.document_version_id != expected_version):
            raise GeneratedVersionError()
        try:
            with self._uow() as tx:
                if not self._repository.lock_request(
                        tx, claim=claim, execution_id=expected_execution,
                        publication=publication):
                    raise GeneratedVersionError()
                current = self._jobs.check_output_claim(
                    tx, job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref)
                if (type(current) is not ClaimedJob or current != claim
                        or current.job_type != "OUTPUT_GENERATE"
                        or current.scope != "PROJECT"
                        or current.project_id is None
                        or current.payload_refs != claim.payload_refs):
                    raise GeneratedVersionError()
                facts = self._repository.commit_generated_version(
                    tx, claim=claim, execution_id=expected_execution,
                    system_actor_id=self._system_actor_id, publication=publication)
                if (type(facts) is not GeneratedVersionFacts
                        or facts.output_request_id != request_id
                        or facts.project_id != claim.project_id
                        or facts.document_id != publication.document_id
                        or facts.document_version_id != publication.document_version_id
                        or facts.file_object_id != publication.file_object_id
                        or facts.plugin_execution_id != expected_execution
                        or facts.version_no < 1):
                    raise GeneratedVersionError()
                if facts.changed:
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=trace_id, event_scope="PROJECT",
                        target_project_id=facts.project_id, actor_type="SYSTEM",
                        actor_id=self._system_actor_id, original_actor_id=None,
                        actor_hint_digest=None,
                        action="OUTPUT_GENERATED_DOCUMENT_VERSION_CREATED",
                        outcome="SUCCESS", target_owner_module="document",
                        target_object_type="DOC-01", target_object_id=facts.document_id,
                        target_version_id=facts.document_version_id,
                        reason_code=None, before_state=None, after_state="AVAILABLE"))
                tx.commit()
                return facts
        except GeneratedVersionError:
            raise
        except (JobLeaseError, IdempotencyError):
            raise GeneratedVersionError() from None
        except Exception:
            raise GeneratedVersionError("SYSTEM_UNAVAILABLE") from None
