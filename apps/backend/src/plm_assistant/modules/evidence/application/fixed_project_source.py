"""Evidence-owned, caller-transaction proof for a policy-scoped PROJECT reference."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.document.application.prove_fixed_source import (
    FixedSourceProofError, VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.project.application.authorization import ProjectActorFacts

from .fixed_source_record import LockedEvidenceSource
from .parsed_node_proof import EvidenceNodeProofError, ParsedNodeEvidenceProofService
from ..domain.locator import EvidenceLocatorError, validate_evidence_locator


class EvidenceFixedSourceError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_RESOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceFixedProjectQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VerifiedProjectEvidence:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_parse_record_id: uuid.UUID | None
    observed_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    observed_state: str = "ELIGIBLE"
    scope: str = "PROJECT"
    verified_by: uuid.UUID | None = None
    verified_project_role: str = ""
    document_category: str = ""


class SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class ProjectPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class EvidenceSourcePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class DocumentSourcePort(Protocol):
    def prove(self, transaction: object, query: DocumentReadQuery, *,
              document_id: uuid.UUID, document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID | None = None) -> VerifiedFixedSource: ...


class EvidenceFixedProjectSourceService:
    def __init__(self, *, sessions: SessionPort, projects: ProjectPort,
                 evidence: EvidenceSourcePort, documents: DocumentSourcePort,
                 allowed_project_roles: frozenset[str] | None = None,
                 required_document_category: str | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (sessions, projects, evidence, documents)):
            raise ValueError("fixed PROJECT Evidence dependencies required")
        roles = (frozenset({"PROJECT_MANAGER"})
                 if allowed_project_roles is None else allowed_project_roles)
        if (type(roles) is not frozenset or not roles
                or not all(type(role) is str and role in {
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                    "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
                } for role in roles)
                or required_document_category is not None and (
                    type(required_document_category) is not str
                    or not 1 <= len(required_document_category) <= 64
                )):
            raise ValueError("validated PROJECT Evidence policy required")
        self._sessions, self._projects = sessions, projects
        self._evidence, self._documents = evidence, documents
        self._allowed_project_roles = roles
        self._required_document_category = required_document_category
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, query: EvidenceFixedProjectQuery,
              evidence_id: uuid.UUID) -> VerifiedProjectEvidence:
        if (transaction is None or type(query) is not EvidenceFixedProjectQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
        try:
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise EvidenceFixedSourceError()
            actor = self._sessions.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise EvidenceFixedSourceError("AUTH_ACCESS_DENIED")
            role = self._projects.actor_facts(
                transaction, user_id=actor, project_id=query.project_id, lock=True,
            )
            if (type(role) is not ProjectActorFacts
                    or role.project_state != "ACTIVE"
                    or role.project_role not in self._allowed_project_roles):
                raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
            source = self._evidence.get_for_trace(
                transaction, scope="PROJECT", project_id=query.project_id,
                evidence_id=evidence_id,
            )
            if (type(source) is not LockedEvidenceSource
                    or source.evidence_id != evidence_id
                    or source.scope != "PROJECT" or source.project_id != query.project_id
                    or type(source.document_id) is not uuid.UUID or source.document_id.int == 0
                    or type(source.document_version_id) is not uuid.UUID
                    or source.document_version_id.int == 0
                    or type(source.lock_version) is not int or source.lock_version < 0
                    or type(source.content_fingerprint) is not bytes
                    or len(source.content_fingerprint) != 32):
                raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
            try:
                locator = validate_evidence_locator(source.locator)
            except EvidenceLocatorError:
                raise EvidenceFixedSourceError("EVIDENCE_RESOLUTION_UNAVAILABLE") from None
            record_id = source.source_parse_record_id
            if locator["locator_type"] == "DOCUMENT":
                if record_id is not None:
                    raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
            elif type(record_id) is not uuid.UUID or record_id.int == 0:
                raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
            document_query = DocumentReadQuery(
                query.session_token, query.trace_id, "PROJECT", query.project_id,
            )
            fixed = self._documents.prove(
                transaction, document_query, document_id=source.document_id,
                document_version_id=source.document_version_id,
                parse_record_id=record_id,
            )
            if (type(fixed) is not VerifiedFixedSource
                    or fixed.facts.document_id != source.document_id
                    or fixed.facts.document_version_id != source.document_version_id
                    or fixed.facts.scope != "PROJECT"
                    or fixed.facts.project_id != query.project_id
                    or (
                        self._required_document_category is None
                        and fixed.facts.document_category == "TEMPLATE"
                    )
                    or (
                        self._required_document_category is not None
                        and fixed.facts.document_category
                        != self._required_document_category
                    )):
                raise EvidenceFixedSourceError("RESOURCE_NOT_FOUND")
            if record_id is None:
                if fixed.parse_record_id is not None:
                    raise EvidenceFixedSourceError()
                try:
                    fingerprint = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise EvidenceFixedSourceError() from None
            else:
                if (fixed.parse_record_id != record_id
                        or type(fixed.result_ref_id) is not uuid.UUID
                        or type(fixed.parser_profile) is not str
                        or type(fixed.parser_version) is not str
                        or type(fixed.result_sha256) is not bytes
                        or type(fixed.parse_content) is not bytes):
                    raise EvidenceFixedSourceError()
                try:
                    source_digest = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise EvidenceFixedSourceError() from None
                parsed = VerifiedParseResult(
                    record_id, source.document_version_id, fixed.result_ref_id,
                    fixed.parser_profile, fixed.parser_version, source_digest,
                    fixed.result_sha256, fixed.parse_content,
                )
                node = ParsedNodeEvidenceProofService.prove_verified(
                    parsed, document_version_id=source.document_version_id,
                    parse_record_id=record_id, locator=locator,
                )
                if node.locator != locator:
                    raise EvidenceFixedSourceError()
                fingerprint = node.content_fingerprint
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or not hmac.compare_digest(fingerprint, source.content_fingerprint)):
                raise EvidenceFixedSourceError("EVIDENCE_FINGERPRINT_MISMATCH")
            return VerifiedProjectEvidence(
                evidence_id, query.project_id, source.document_id,
                source.document_version_id, record_id, source.lock_version,
                fingerprint, verified_by=actor,
                verified_project_role=role.project_role,
                document_category=fixed.facts.document_category,
            )
        except EvidenceFixedSourceError:
            raise
        except FixedSourceProofError as error:
            if error.code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED",
                              "RESOURCE_NOT_FOUND"):
                raise EvidenceFixedSourceError(error.code) from None
            if error.code == "FILE_INTEGRITY_MISMATCH":
                raise EvidenceFixedSourceError("EVIDENCE_FINGERPRINT_MISMATCH") from None
            raise EvidenceFixedSourceError() from None
        except EvidenceNodeProofError:
            raise EvidenceFixedSourceError() from None
        except Exception:
            raise EvidenceFixedSourceError() from None
