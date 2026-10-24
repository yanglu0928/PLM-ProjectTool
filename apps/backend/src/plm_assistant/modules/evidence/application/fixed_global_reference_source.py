"""Admin-only GLOBAL Evidence proof for ReferenceSolution source admission."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.document.application.prove_fixed_source import (
    FixedSourceProofError, VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts, DocumentReadQuery,
)
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult

from .fixed_source_record import LockedEvidenceSource
from .parsed_node_proof import EvidenceNodeProofError, ParsedNodeEvidenceProofService
from ..domain.locator import EvidenceLocatorError, validate_evidence_locator


class GlobalReferenceEvidenceError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_RESOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GlobalReferenceEvidenceQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VerifiedGlobalReferenceEvidence:
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_parse_record_id: uuid.UUID | None
    content_fingerprint: bytes = field(repr=False)
    authorized_admin_id: uuid.UUID
    scope: str = "GLOBAL"
    project_id: None = None


class SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class AdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class EvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class DocumentPort(Protocol):
    def prove(self, transaction: object, query: DocumentReadQuery, *,
              document_id: uuid.UUID, document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID | None = None) -> VerifiedFixedSource: ...


class EvidenceFixedGlobalReferenceService:
    def __init__(self, *, sessions: SessionPort, admins: AdminPort,
                 evidence: EvidencePort, documents: DocumentPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (sessions, admins, evidence, documents)):
            raise ValueError("GLOBAL Reference Evidence proof dependencies required")
        self._sessions, self._admins = sessions, admins
        self._evidence, self._documents = evidence, documents
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, query: GlobalReferenceEvidenceQuery,
              evidence_id: uuid.UUID) -> VerifiedGlobalReferenceEvidence:
        if (transaction is None or type(query) is not GlobalReferenceEvidenceQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
        try:
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise GlobalReferenceEvidenceError()
            actor = self._sessions.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise GlobalReferenceEvidenceError("AUTH_ACCESS_DENIED")
            admin = self._admins.authorized_admin(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(admin) is not uuid.UUID or admin != actor:
                raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
            source = self._evidence.get_for_trace(
                transaction, scope="GLOBAL", project_id=None, evidence_id=evidence_id,
            )
            if (type(source) is not LockedEvidenceSource
                    or source.evidence_id != evidence_id
                    or source.scope != "GLOBAL" or source.project_id is not None
                    or type(source.document_id) is not uuid.UUID or source.document_id.int == 0
                    or type(source.document_version_id) is not uuid.UUID
                    or source.document_version_id.int == 0
                    or type(source.lock_version) is not int or source.lock_version < 0
                    or type(source.content_fingerprint) is not bytes
                    or len(source.content_fingerprint) != 32):
                raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
            try:
                locator = validate_evidence_locator(source.locator)
            except EvidenceLocatorError:
                raise GlobalReferenceEvidenceError() from None
            parse_id = source.source_parse_record_id
            if locator["locator_type"] == "DOCUMENT":
                if parse_id is not None:
                    raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
            elif type(parse_id) is not uuid.UUID or parse_id.int == 0:
                raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
            fixed = self._documents.prove(
                transaction,
                DocumentReadQuery(query.session_token, query.trace_id, "GLOBAL", None),
                document_id=source.document_id,
                document_version_id=source.document_version_id,
                parse_record_id=parse_id,
            )
            if (type(fixed) is not VerifiedFixedSource
                    or type(fixed.facts) is not DocumentEvidenceSourceFacts
                    or fixed.facts.document_id != source.document_id
                    or fixed.facts.document_version_id != source.document_version_id
                    or fixed.facts.scope != "GLOBAL" or fixed.facts.project_id is not None
                    or fixed.facts.document_category not in (
                        "REFERENCE_MATERIAL", "STANDARD_CAPABILITY")):
                raise GlobalReferenceEvidenceError("RESOURCE_NOT_FOUND")
            if parse_id is None:
                if fixed.parse_record_id is not None:
                    raise GlobalReferenceEvidenceError()
                try:
                    fingerprint = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise GlobalReferenceEvidenceError() from None
            else:
                if (fixed.parse_record_id != parse_id
                        or type(fixed.result_ref_id) is not uuid.UUID
                        or type(fixed.parser_profile) is not str
                        or type(fixed.parser_version) is not str
                        or type(fixed.result_sha256) is not bytes
                        or type(fixed.parse_content) is not bytes):
                    raise GlobalReferenceEvidenceError()
                try:
                    source_digest = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise GlobalReferenceEvidenceError() from None
                parsed = VerifiedParseResult(
                    parse_id, source.document_version_id, fixed.result_ref_id,
                    fixed.parser_profile, fixed.parser_version, source_digest,
                    fixed.result_sha256, fixed.parse_content,
                )
                node = ParsedNodeEvidenceProofService.prove_verified(
                    parsed, document_version_id=source.document_version_id,
                    parse_record_id=parse_id, locator=locator,
                )
                if node.locator != locator:
                    raise GlobalReferenceEvidenceError()
                fingerprint = node.content_fingerprint
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or not hmac.compare_digest(fingerprint, source.content_fingerprint)):
                raise GlobalReferenceEvidenceError("EVIDENCE_FINGERPRINT_MISMATCH")
            return VerifiedGlobalReferenceEvidence(
                evidence_id, source.document_id, source.document_version_id,
                parse_id, fingerprint, actor,
            )
        except GlobalReferenceEvidenceError:
            raise
        except FixedSourceProofError as error:
            if error.code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED",
                              "RESOURCE_NOT_FOUND"):
                raise GlobalReferenceEvidenceError(error.code) from None
            if error.code == "FILE_INTEGRITY_MISMATCH":
                raise GlobalReferenceEvidenceError("EVIDENCE_FINGERPRINT_MISMATCH") from None
            raise GlobalReferenceEvidenceError() from None
        except EvidenceNodeProofError:
            raise GlobalReferenceEvidenceError() from None
        except Exception:
            raise GlobalReferenceEvidenceError() from None
