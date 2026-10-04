"""Evidence-owned GLOBAL standard reference for one authorized target project."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.document.application.prove_fixed_source import VerifiedFixedSource
from plm_assistant.modules.document.application.prove_global_standard import (
    GlobalStandardProofError, GlobalStandardReferenceQuery,
)
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.project.application.authorization import ProjectActorFacts

from .fixed_source_record import LockedEvidenceSource
from .parsed_node_proof import EvidenceNodeProofError, ParsedNodeEvidenceProofService
from ..domain.locator import EvidenceLocatorError, validate_evidence_locator


class StandardEvidenceError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_RESOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StandardEvidenceQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    target_project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VerifiedStandardEvidence:
    evidence_id: uuid.UUID
    target_project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_parse_record_id: uuid.UUID | None
    observed_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    observed_state: str = "ELIGIBLE"
    scope: str = "GLOBAL"
    source_project_id: None = None


class SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class ProjectPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class EvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class StandardDocumentPort(Protocol):
    def prove(self, transaction: object, query: GlobalStandardReferenceQuery, *,
              document_id: uuid.UUID, document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID | None = None) -> VerifiedFixedSource: ...


class EvidenceFixedGlobalStandardService:
    def __init__(self, *, sessions: SessionPort, projects: ProjectPort,
                 evidence: EvidencePort, standards: StandardDocumentPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (sessions, projects, evidence, standards)):
            raise ValueError("GLOBAL standard Evidence dependencies required")
        self._sessions, self._projects = sessions, projects
        self._evidence, self._standards = evidence, standards
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, query: StandardEvidenceQuery,
              evidence_id: uuid.UUID) -> VerifiedStandardEvidence:
        if (transaction is None or type(query) is not StandardEvidenceQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.target_project_id) is not uuid.UUID
                or query.target_project_id.int == 0
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise StandardEvidenceError("RESOURCE_NOT_FOUND")
        try:
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise StandardEvidenceError()
            actor = self._sessions.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise StandardEvidenceError("AUTH_ACCESS_DENIED")
            role = self._projects.actor_facts(
                transaction, user_id=actor, project_id=query.target_project_id,
                lock=True,
            )
            if (type(role) is not ProjectActorFacts or role.project_state != "ACTIVE"
                    or role.project_role != "PROJECT_MANAGER"):
                raise StandardEvidenceError("RESOURCE_NOT_FOUND")
            source = self._evidence.get_for_trace(
                transaction, scope="GLOBAL", project_id=None, evidence_id=evidence_id,
            )
            if (type(source) is not LockedEvidenceSource
                    or source.evidence_id != evidence_id or source.scope != "GLOBAL"
                    or source.project_id is not None
                    or type(source.document_id) is not uuid.UUID or source.document_id.int == 0
                    or type(source.document_version_id) is not uuid.UUID
                    or source.document_version_id.int == 0
                    or type(source.lock_version) is not int or source.lock_version < 0
                    or type(source.content_fingerprint) is not bytes
                    or len(source.content_fingerprint) != 32):
                raise StandardEvidenceError("RESOURCE_NOT_FOUND")
            try:
                locator = validate_evidence_locator(source.locator)
            except EvidenceLocatorError:
                raise StandardEvidenceError() from None
            record_id = source.source_parse_record_id
            if locator["locator_type"] == "DOCUMENT":
                if record_id is not None:
                    raise StandardEvidenceError("RESOURCE_NOT_FOUND")
            elif type(record_id) is not uuid.UUID or record_id.int == 0:
                raise StandardEvidenceError("RESOURCE_NOT_FOUND")
            fixed = self._standards.prove(
                transaction, GlobalStandardReferenceQuery(
                    query.session_token, query.trace_id, query.target_project_id,
                ), document_id=source.document_id,
                document_version_id=source.document_version_id,
                parse_record_id=record_id,
            )
            if (type(fixed) is not VerifiedFixedSource
                    or fixed.facts.document_id != source.document_id
                    or fixed.facts.document_version_id != source.document_version_id
                    or fixed.facts.scope != "GLOBAL" or fixed.facts.project_id is not None
                    or fixed.facts.document_category != "STANDARD_CAPABILITY"):
                raise StandardEvidenceError("RESOURCE_NOT_FOUND")
            if record_id is None:
                if fixed.parse_record_id is not None:
                    raise StandardEvidenceError()
                try:
                    fingerprint = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise StandardEvidenceError() from None
            else:
                if (fixed.parse_record_id != record_id
                        or type(fixed.result_ref_id) is not uuid.UUID
                        or type(fixed.parser_profile) is not str
                        or type(fixed.parser_version) is not str
                        or type(fixed.result_sha256) is not bytes
                        or type(fixed.parse_content) is not bytes):
                    raise StandardEvidenceError()
                try:
                    source_digest = bytes.fromhex(fixed.facts.content_sha256)
                except (TypeError, ValueError):
                    raise StandardEvidenceError() from None
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
                    raise StandardEvidenceError()
                fingerprint = node.content_fingerprint
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or not hmac.compare_digest(fingerprint, source.content_fingerprint)):
                raise StandardEvidenceError("EVIDENCE_FINGERPRINT_MISMATCH")
            return VerifiedStandardEvidence(
                evidence_id, query.target_project_id, source.document_id,
                source.document_version_id, record_id, source.lock_version,
                fingerprint,
            )
        except StandardEvidenceError:
            raise
        except GlobalStandardProofError as error:
            if error.code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED",
                              "RESOURCE_NOT_FOUND"):
                raise StandardEvidenceError(error.code) from None
            if error.code == "FILE_INTEGRITY_MISMATCH":
                raise StandardEvidenceError("EVIDENCE_FINGERPRINT_MISMATCH") from None
            raise StandardEvidenceError() from None
        except EvidenceNodeProofError:
            raise StandardEvidenceError() from None
        except Exception:
            raise StandardEvidenceError() from None
