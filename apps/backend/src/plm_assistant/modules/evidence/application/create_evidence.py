"""Create a candidate only after source proof and in-transaction authorization."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadQuery, DocumentVersionView,
)
from plm_assistant.modules.evidence.application.document_source_proof import EvidenceDocumentProof
from plm_assistant.modules.evidence.application.parsed_node_proof import EvidenceParsedNodeProof
from plm_assistant.modules.evidence.domain.locator import EvidenceLocatorError, validate_evidence_locator
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)


class EvidenceCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateEvidence:
    actor_id: uuid.UUID
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    locator: dict[str, object]
    display_label: str
    display_excerpt: str | None = None
    parse_record_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CreatedEvidence:
    evidence_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    locator: dict[str, object]
    content_fingerprint: bytes = field(repr=False)
    display_label: str
    display_excerpt: str | None
    created_at: datetime
    eligibility_state: str = "CANDIDATE"
    etag: str = '"v0"'


class EvidenceCreateAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               document_id: uuid.UUID, operation: str) -> None: ...


class EvidenceVersionPort(Protocol):
    def get_version_for_trace(self, transaction: object, query: DocumentReadQuery,
                              document_id: uuid.UUID,
                              document_version_id: uuid.UUID) -> DocumentVersionView: ...


class EvidenceDocumentProofPort(Protocol):
    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID, locator: object) -> EvidenceDocumentProof: ...


class EvidenceNodeProofPort(Protocol):
    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID, parse_record_id: uuid.UUID,
              locator: object) -> EvidenceParsedNodeProof: ...


class EvidenceRepositoryPort(Protocol):
    def create(self, transaction: object, *, command: CreateEvidence,
               locator: dict[str, object], fingerprint: bytes) -> tuple[uuid.UUID, datetime]: ...
    def replay(self, transaction: object, evidence_id: uuid.UUID, *,
               command: CreateEvidence, locator: dict[str, object],
               fingerprint: bytes) -> datetime | None: ...


class EvidenceReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class EvidenceCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: EvidenceCreateAccessPort,
                 versions: EvidenceVersionPort, document_proof: EvidenceDocumentProofPort,
                 node_proof: EvidenceNodeProofPort, repository: EvidenceRepositoryPort,
                 receipts: EvidenceReceiptPort, audit: AuditService) -> None:
        if any(item is None for item in (unit_of_work, access, versions, document_proof,
                                         node_proof, repository, receipts, audit)):
            raise ValueError("Evidence create dependencies are required")
        self._uow, self._access, self._versions = unit_of_work, access, versions
        self._document_proof, self._node_proof = document_proof, node_proof
        self._repository, self._receipts, self._audit = repository, receipts, audit

    def create(self, command: CreateEvidence, *, idempotency_key: str) -> CreatedEvidence:
        locator = self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "scope": command.scope, "project_id": str(command.project_id) if command.project_id else None,
                "document_id": str(command.document_id), "document_version_id": str(command.document_version_id),
                "locator": locator, "display_label": command.display_label,
                "display_excerpt": command.display_excerpt,
                "parse_record_id": str(command.parse_record_id) if command.parse_record_id else None,
            })
            query = DocumentReadQuery(command.session_token, command.trace_id,
                                      command.scope, command.project_id)
            with self._uow() as tx:
                self._require_access(tx, command)
            if locator["locator_type"] == "DOCUMENT":
                if command.parse_record_id is not None:
                    raise EvidenceCreateError("VALIDATION_FAILED")
                proof = self._document_proof.prove(
                    query, document_id=command.document_id,
                    document_version_id=command.document_version_id, locator=locator,
                )
            else:
                if command.parse_record_id is None:
                    raise EvidenceCreateError("VALIDATION_FAILED")
                proof = self._node_proof.prove(
                    query, document_id=command.document_id,
                    document_version_id=command.document_version_id,
                    parse_record_id=command.parse_record_id, locator=locator,
                )
            if (type(proof) not in (EvidenceDocumentProof, EvidenceParsedNodeProof)
                    or proof.document_version_id != command.document_version_id
                    or proof.locator != locator
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32):
                raise EvidenceCreateError("EVIDENCE_RESOLUTION_UNAVAILABLE")
            with self._uow() as tx:
                self._require_access(tx, command)
                version = self._versions.get_version_for_trace(
                    tx, query, command.document_id, command.document_version_id,
                )
                if (type(version) is not DocumentVersionView
                        or version.document_id != command.document_id
                        or version.document_version_id != command.document_version_id
                        or version.availability_state != "AVAILABLE"):
                    raise EvidenceCreateError("RESOURCE_NOT_FOUND")
                if locator["locator_type"] == "DOCUMENT" and not hmac.compare_digest(
                    version.content_sha256, proof.content_fingerprint.hex()
                ):
                    raise EvidenceCreateError("EVIDENCE_RESOLUTION_UNAVAILABLE")
                if (type(proof) is EvidenceParsedNodeProof and (
                        type(proof.source_sha256) is not bytes
                        or len(proof.source_sha256) != 32
                        or not hmac.compare_digest(version.content_sha256,
                                                   proof.source_sha256.hex()))):
                    raise EvidenceCreateError("EVIDENCE_RESOLUTION_UNAVAILABLE")
                scope = IdempotencyScope.from_key(
                    actor_id=command.actor_id, project_id=command.project_id,
                    operation="V1_EVIDENCE_CREATE", key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != "V1_EVIDENCE" or replay.status_code != 201:
                        raise EvidenceCreateError("EVIDENCE_UNAVAILABLE")
                    created_at = self._repository.replay(
                        tx, replay.ref_id, command=command, locator=locator,
                        fingerprint=proof.content_fingerprint,
                    )
                    if created_at is None:
                        raise EvidenceCreateError("EVIDENCE_UNAVAILABLE")
                    return self._view(replay.ref_id, command, locator, proof.content_fingerprint, created_at)
                evidence_id, created_at = self._repository.create(
                    tx, command=command, locator=locator,
                    fingerprint=proof.content_fingerprint,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="DEPLOYMENT" if command.scope == "GLOBAL" else "PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=command.actor_id, original_actor_id=None,
                    actor_hint_digest=None, action="EVIDENCE_CREATED", outcome="SUCCESS",
                    target_owner_module="evidence", target_object_type="EVD-01",
                    target_object_id=evidence_id,
                    after_state="CANDIDATE",
                ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult("V1_EVIDENCE", evidence_id, 201),
                )
                tx.commit()
                return self._view(evidence_id, command, locator, proof.content_fingerprint, created_at)
        except IdempotencyError as error:
            raise EvidenceCreateError(error.code) from None

    @staticmethod
    def _validate(command: CreateEvidence) -> dict[str, object]:
        if (type(command) is not CreateEvidence
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.actor_id, command.trace_id, command.document_id,
                    command.document_version_id))
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or command.scope not in ("GLOBAL", "PROJECT")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and (type(command.project_id) is not uuid.UUID
                                                    or command.project_id.int == 0)
                or command.parse_record_id is not None and (
                    type(command.parse_record_id) is not uuid.UUID or command.parse_record_id.int == 0)
                or type(command.display_label) is not str
                or not 1 <= len(command.display_label) <= 255
                or command.display_label != command.display_label.strip()
                or any(ord(char) < 32 for char in command.display_label)
                or command.display_excerpt is not None and (
                    type(command.display_excerpt) is not str
                    or not 1 <= len(command.display_excerpt) <= 500)):
            raise EvidenceCreateError("VALIDATION_FAILED")
        try:
            return validate_evidence_locator(command.locator)
        except EvidenceLocatorError:
            raise EvidenceCreateError("EVIDENCE_LOCATOR_INVALID") from None

    def _require_access(self, tx: object, command: CreateEvidence) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, document_id=command.document_id,
            operation="V1_EVIDENCE_CREATE",
        )

    @staticmethod
    def _view(evidence_id: uuid.UUID, command: CreateEvidence, locator: dict[str, object],
              fingerprint: bytes, created_at: datetime) -> CreatedEvidence:
        return CreatedEvidence(
            evidence_id, command.scope, command.project_id, command.document_id,
            command.document_version_id, locator, fingerprint,
            command.display_label, command.display_excerpt, created_at,
        )
