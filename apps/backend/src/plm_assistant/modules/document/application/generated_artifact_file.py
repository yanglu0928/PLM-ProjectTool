"""SYSTEM-owned Output file promotion coordinating storage and database owners."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.application.generated_artifact_version import (
    GeneratedDocumentVersion, GeneratedVersionError, OutputGeneratedDocumentVersionOwner,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    FileContentProof, LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.complete_generation import (
    OutputArtifactPublication, OutputGenerationCompletionOwner,
    OutputGenerationCompletionFacts,
)
from plm_assistant.modules.output.application.fail_generation import OutputGenerationFailureOwner
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


class GeneratedFilePublicationError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_FILE_PUBLICATION_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GeneratedFileRequestFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    execution_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    request_state: str
    request_lock_version: int


@dataclass(frozen=True, slots=True)
class GeneratedFileSnapshot:
    request: GeneratedFileRequestFacts
    document_id: uuid.UUID
    file_object_id: uuid.UUID
    file_state: str
    file_lock_version: int
    storage_locator: str
    staging_locator: str
    final_locator: str
    sha256: bytes
    size_bytes: int
    media_type: str


@dataclass(frozen=True, slots=True)
class GeneratedFilePublicationFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    file_object_id: uuid.UUID
    proof: FileContentProof
    completion: OutputGenerationCompletionFacts


class GeneratedFilePublicationJobsPort(Protocol):
    def check_output_claim(self, transaction: object, *, job_id: uuid.UUID,
                           fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class GeneratedFilePublicationRepositoryPort(Protocol):
    def lock_request(self, transaction: object, *, claim: ClaimedJob,
                     publication: OutputArtifactPublication) -> GeneratedFileRequestFacts: ...
    def snapshot(self, transaction: object, *, claim: ClaimedJob,
                 publication: OutputArtifactPublication,
                 request: GeneratedFileRequestFacts) -> GeneratedFileSnapshot: ...
    def mark_available(self, transaction: object, *, claim: ClaimedJob,
                       publication: OutputArtifactPublication,
                       expected: GeneratedFileSnapshot,
                       system_actor_id: uuid.UUID) -> GeneratedFileSnapshot: ...


class OutputGeneratedFilePublicationOwner:
    """Promote verified bytes, publish FileObject, then invoke version and Output owners."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 jobs: GeneratedFilePublicationJobsPort,
                 repository: GeneratedFilePublicationRepositoryPort,
                 storage: LocalFileStorage, audit: AuditService,
                 version_owner: OutputGeneratedDocumentVersionOwner,
                 completion_owner: OutputGenerationCompletionOwner,
                 system_actor_id: uuid.UUID) -> None:
        if (unit_of_work is None or jobs is None or repository is None or storage is None
                or audit is None or version_owner is None or completion_owner is None
                or type(system_actor_id) is not uuid.UUID or not system_actor_id.int):
            raise ValueError("generated file publication dependencies are required")
        self._uow, self._jobs, self._repo = unit_of_work, jobs, repository
        self._storage, self._audit = storage, audit
        self._version_owner, self._completion_owner = version_owner, completion_owner
        self._system_actor_id = system_actor_id

    def publish(self, claim: ClaimedJob, *, worker_ref: str,
                publication: OutputArtifactPublication) -> GeneratedFilePublicationFacts:
        try:
            request_id, _, _ = OutputGenerationFailureOwner._validate_claim(claim, worker_ref)
        except Exception:
            raise GeneratedFilePublicationError() from None
        if (type(publication) is not OutputArtifactPublication
                or claim.job_type != "OUTPUT_GENERATE" or claim.scope != "PROJECT"
                or publication.plugin_execution_id != uuid.uuid5(
                    claim.job_id, "output-generation:" + str(claim.fencing_token))):
            raise GeneratedFilePublicationError()
        try:
            with self._uow() as tx:
                request = self._repo.lock_request(
                    tx, claim=claim, publication=publication)
                self._validate_request(request, claim, request_id, publication)
                if request.request_state == "GENERATING":
                    self._check_claim(tx, claim, worker_ref)
                elif request.request_state != "SUCCEEDED":
                    raise GeneratedFilePublicationError()
                snapshot = self._repo.snapshot(
                    tx, claim=claim, publication=publication, request=request)
                self._validate_snapshot(snapshot, claim, publication)
                tx.commit()

            proof = self._prove_and_promote(snapshot, publication)
            if request.request_state == "SUCCEEDED":
                completion = self._completion_owner.complete(
                    claim, worker_ref=worker_ref, publication=publication)
                return GeneratedFilePublicationFacts(
                    request_id, claim.project_id, publication.document_id,
                    publication.file_object_id, proof, completion)

            with self._uow() as tx:
                current_request = self._repo.lock_request(
                    tx, claim=claim, publication=publication)
                self._validate_request(current_request, claim, request_id, publication)
                self._check_claim(tx, claim, worker_ref)
                current = self._repo.snapshot(
                    tx, claim=claim, publication=publication, request=current_request)
                self._validate_snapshot(current, claim, publication)
                if not self._same_binding(current, snapshot):
                    raise GeneratedFilePublicationError()
                available = self._repo.mark_available(
                    tx, claim=claim, publication=publication,
                    expected=current, system_actor_id=self._system_actor_id)
                if (available.file_state != "AVAILABLE"
                        or available.storage_locator != snapshot.final_locator):
                    raise GeneratedFilePublicationError()
                if current.file_state != "AVAILABLE":
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=request.trace_id, event_scope="PROJECT",
                        target_project_id=request.project_id, actor_type="SYSTEM",
                        actor_id=self._system_actor_id,
                        original_actor_id=request.requested_by,
                        actor_hint_digest=None, action="OUTPUT_GENERATED_FILE_PUBLISHED",
                        outcome="SUCCESS", target_owner_module="document",
                        target_object_type="DOC-01", target_object_id=publication.document_id,
                        target_version_id=None, reason_code=None,
                        before_state="STAGED", after_state="AVAILABLE"))
                tx.commit()

            generated = GeneratedDocumentVersion(
                document_id=publication.document_id,
                document_version_id=publication.document_version_id,
                file_object_id=publication.file_object_id,
                plugin_execution_id=publication.plugin_execution_id,
                sha256=publication.sha256, size_bytes=publication.size_bytes,
                media_type=publication.media_type)
            self._version_owner.commit(claim, worker_ref=worker_ref, publication=generated)
            completion = self._completion_owner.complete(
                claim, worker_ref=worker_ref, publication=publication)
            return GeneratedFilePublicationFacts(
                request_id, claim.project_id, publication.document_id,
                publication.file_object_id, proof, completion)
        except GeneratedFilePublicationError:
            raise
        except (GeneratedVersionError, JobLeaseError, IdempotencyError):
            raise GeneratedFilePublicationError() from None
        except (LocalStorageError, OSError):
            raise GeneratedFilePublicationError("OUTPUT_STORAGE_UNAVAILABLE") from None
        except Exception:
            raise GeneratedFilePublicationError("SYSTEM_UNAVAILABLE") from None

    def _prove_and_promote(self, snapshot: GeneratedFileSnapshot,
                           publication: OutputArtifactPublication) -> FileContentProof:
        if snapshot.file_state == "AVAILABLE":
            if snapshot.storage_locator != snapshot.final_locator:
                raise GeneratedFilePublicationError()
            return self._storage.verify_content(
                snapshot.final_locator, expected_sha256=publication.sha256,
                expected_size=publication.size_bytes, max_bytes=134217728)
        if (snapshot.file_state != "STAGED"
                or snapshot.storage_locator != snapshot.staging_locator):
            raise GeneratedFilePublicationError()
        inspection = self._storage.inspect_recovery(
            snapshot.staging_locator, snapshot.final_locator,
            expected_sha256=publication.sha256, expected_size=publication.size_bytes,
            max_bytes=134217728)
        if inspection.shape == "STAGE_ONLY":
            return self._storage.publish_verified(
                snapshot.staging_locator, snapshot.final_locator,
                expected_sha256=publication.sha256, expected_size=publication.size_bytes,
                max_bytes=134217728)
        if inspection.shape == "FINAL_VERIFIED":
            return self._storage.recover_verified_final(
                snapshot.staging_locator, snapshot.final_locator,
                expected_sha256=publication.sha256, expected_size=publication.size_bytes,
                max_bytes=134217728)
        if inspection.shape == "LINKED_PAIR":
            return self._storage.recover_linked_pair(
                snapshot.staging_locator, snapshot.final_locator,
                expected_sha256=publication.sha256, expected_size=publication.size_bytes,
                max_bytes=134217728)
        raise GeneratedFilePublicationError("OUTPUT_STORAGE_RECOVERY_REQUIRED")

    @staticmethod
    def _validate_request(request: GeneratedFileRequestFacts, claim: ClaimedJob,
                          request_id: uuid.UUID,
                          publication: OutputArtifactPublication) -> None:
        if (type(request) is not GeneratedFileRequestFacts
                or request.output_request_id != request_id
                or request.project_id != claim.project_id
                or request.job_id != claim.job_id
                or request.execution_id != publication.plugin_execution_id
                or request.request_state not in {"GENERATING", "SUCCEEDED"}
                or request.request_lock_version < 1):
            raise GeneratedFilePublicationError()

    @staticmethod
    def _validate_snapshot(snapshot: GeneratedFileSnapshot, claim: ClaimedJob,
                           publication: OutputArtifactPublication) -> None:
        if (type(snapshot) is not GeneratedFileSnapshot
                or snapshot.request.job_id != claim.job_id
                or snapshot.request.project_id != claim.project_id
                or snapshot.document_id != publication.document_id
                or snapshot.file_object_id != publication.file_object_id
                or snapshot.sha256 != publication.sha256
                or snapshot.size_bytes != publication.size_bytes
                or snapshot.media_type != publication.media_type
                or snapshot.file_state not in {"STAGED", "AVAILABLE"}
                or snapshot.storage_locator not in {
                    snapshot.staging_locator, snapshot.final_locator}):
            raise GeneratedFilePublicationError()

    @staticmethod
    def _same_binding(left: GeneratedFileSnapshot,
                      right: GeneratedFileSnapshot) -> bool:
        return (left.request == right.request
                and left.document_id == right.document_id
                and left.file_object_id == right.file_object_id
                and left.staging_locator == right.staging_locator
                and left.final_locator == right.final_locator
                and left.sha256 == right.sha256
                and left.size_bytes == right.size_bytes
                and left.media_type == right.media_type
                and (left.file_state == right.file_state
                     or (left.file_state == "STAGED"
                         and right.file_state == "AVAILABLE"
                         and right.storage_locator == right.final_locator)))

    def _check_claim(self, tx: object, claim: ClaimedJob, worker_ref: str) -> None:
        current = self._jobs.check_output_claim(
            tx, job_id=claim.job_id, fencing_token=claim.fencing_token,
            worker_ref=worker_ref)
        if (type(current) is not ClaimedJob or current != claim
                or current.job_type != "OUTPUT_GENERATE"
                or current.project_id != claim.project_id
                or current.payload_refs != claim.payload_refs):
            raise GeneratedFilePublicationError()
