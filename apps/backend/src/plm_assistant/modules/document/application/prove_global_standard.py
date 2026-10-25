"""Narrow GLOBAL standard reference proof; never a general document read Port."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ProjectActorFacts

from .prove_fixed_source import VerifiedFixedSource
from .read_documents import (
    DocumentDownloadSource, DocumentEvidenceSourceFacts, DocumentVersionView,
    DocumentView,
)
from .read_parse_result import FixedParseResultSource


class GlobalStandardProofError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GlobalStandardReferenceQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    target_project_id: uuid.UUID


class SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class ProjectPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class StandardDocumentPort(Protocol):
    def get_version_for_trace(self, transaction: object, *, scope: str,
                              project_id: uuid.UUID | None, document_id: uuid.UUID,
                              document_version_id: uuid.UUID) -> DocumentVersionView | None: ...
    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None, document_id: uuid.UUID) -> DocumentView | None: ...
    def get_download_source(self, transaction: object, *, scope: str,
                            project_id: uuid.UUID | None, document_id: uuid.UUID,
                            document_version_id: uuid.UUID,
                            actor_user_id: uuid.UUID) -> DocumentDownloadSource | None: ...


class StandardFilePort(Protocol):
    def open_verified_snapshot(self, locator: str, *, expected_sha256: bytes,
                               expected_size: int, max_bytes: int) -> object: ...


class StandardParsePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None, document_version_id: uuid.UUID,
                      parse_record_id: uuid.UUID) -> FixedParseResultSource | None: ...


class StandardParseBytesPort(Protocol):
    def read_verified(self, *, scope: str, project_id: uuid.UUID | None,
                      result_ref_id: uuid.UUID, expected_locator: str,
                      expected_sha256: bytes, expected_size: int) -> bytes: ...


class GlobalStandardReferenceProofService:
    def __init__(self, *, sessions: SessionPort, projects: ProjectPort,
                 license_guard: LicensePort, documents: StandardDocumentPort,
                 files: StandardFilePort, parses: StandardParsePort,
                 parse_bytes: StandardParseBytesPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                sessions, projects, license_guard, documents, files, parses, parse_bytes)):
            raise ValueError("GLOBAL standard proof dependencies required")
        self._sessions, self._projects, self._guard = sessions, projects, license_guard
        self._documents, self._files = documents, files
        self._parses, self._parse_bytes = parses, parse_bytes
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, query: GlobalStandardReferenceQuery, *,
              document_id: uuid.UUID, document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID | None = None) -> VerifiedFixedSource:
        if (transaction is None or type(query) is not GlobalStandardReferenceQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.target_project_id) is not uuid.UUID
                or query.target_project_id.int == 0
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(document_version_id) is not uuid.UUID or document_version_id.int == 0
                or parse_record_id is not None and (
                    type(parse_record_id) is not uuid.UUID or parse_record_id.int == 0)):
            raise GlobalStandardProofError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise GlobalStandardProofError()
            actor = self._sessions.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise GlobalStandardProofError("AUTH_ACCESS_DENIED")
            role = self._projects.actor_facts(
                transaction, user_id=actor, project_id=query.target_project_id,
                lock=True,
            )
            if (type(role) is not ProjectActorFacts or role.project_state != "ACTIVE"
                    or role.project_role != "PROJECT_MANAGER"):
                raise GlobalStandardProofError("RESOURCE_NOT_FOUND")
            version = self._documents.get_version_for_trace(
                transaction, scope="GLOBAL", project_id=None,
                document_id=document_id, document_version_id=document_version_id,
            )
            document = self._documents.get(
                transaction, scope="GLOBAL", project_id=None, document_id=document_id,
            )
            if (type(version) is not DocumentVersionView
                    or version.document_id != document_id
                    or version.document_version_id != document_version_id
                    or version.availability_state != "AVAILABLE"
                    or type(document) is not DocumentView
                    or document.document_id != document_id
                    or document.scope != "GLOBAL" or document.project_id is not None
                    or document.document_state not in ("ACTIVE", "ARCHIVED")
                    or document.document_category != "STANDARD_CAPABILITY"):
                raise GlobalStandardProofError("RESOURCE_NOT_FOUND")
            source = self._documents.get_download_source(
                transaction, scope="GLOBAL", project_id=None,
                document_id=document_id, document_version_id=document_version_id,
                actor_user_id=actor,
            )
            if (type(source) is not DocumentDownloadSource
                    or source.actor_user_id != actor
                    or source.document_id != document_id
                    or source.document_version_id != document_version_id
                    or source.scope != "GLOBAL" or source.project_id is not None
                    or type(source.content_sha256) is not bytes
                    or len(source.content_sha256) != 32
                    or version.content_sha256 != source.content_sha256.hex()
                    or version.size_bytes != source.size_bytes
                    or version.detected_mime != source.detected_mime):
                raise GlobalStandardProofError("RESOURCE_NOT_FOUND")
            try:
                with self._files.open_verified_snapshot(
                        source.storage_locator, expected_sha256=source.content_sha256,
                        expected_size=source.size_bytes, max_bytes=100_000_000):
                    pass
            except Exception:
                raise GlobalStandardProofError("FILE_INTEGRITY_MISMATCH") from None
            facts = DocumentEvidenceSourceFacts(
                document_id, document_version_id, "GLOBAL", None,
                document.document_category, document.document_state,
                source.content_sha256.hex(),
            )
            if parse_record_id is None:
                return VerifiedFixedSource(facts)
            parse = self._parses.get_for_trace(
                transaction, scope="GLOBAL", project_id=None,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id,
            )
            if (type(parse) is not FixedParseResultSource
                    or parse.parse_record_id != parse_record_id
                    or parse.document_version_id != document_version_id
                    or parse.scope != "GLOBAL" or parse.project_id is not None):
                raise GlobalStandardProofError("RESOURCE_NOT_FOUND")
            parse.__post_init__()
            try:
                content = self._parse_bytes.read_verified(
                    scope="GLOBAL", project_id=None,
                    result_ref_id=parse.result_ref_id,
                    expected_locator=parse.storage_locator,
                    expected_sha256=parse.result_sha256,
                    expected_size=parse.size_bytes,
                )
            except Exception:
                raise GlobalStandardProofError("FILE_INTEGRITY_MISMATCH") from None
            if (type(content) is not bytes or len(content) != parse.size_bytes
                    or not hmac.compare_digest(hashlib.sha256(content).digest(),
                                               parse.result_sha256)):
                raise GlobalStandardProofError("FILE_INTEGRITY_MISMATCH")
            try:
                payload = json.loads(content, object_pairs_hook=_unique_object)
            except (ValueError, UnicodeDecodeError, TypeError):
                raise GlobalStandardProofError("PARSER_RESULT_INVALID") from None
            if (type(payload) is not dict or payload.get("schema_version") != "1"
                    or payload.get("document_version_id") != str(document_version_id)
                    or payload.get("source_sha256") != source.content_sha256.hex()
                    or payload.get("parser_profile") != parse.parser_profile
                    or payload.get("parser_version") != parse.parser_version
                    or type(payload.get("nodes")) is not list):
                raise GlobalStandardProofError("PARSER_RESULT_INVALID")
            return VerifiedFixedSource(
                facts, parse_record_id, parse.result_ref_id,
                parse.parser_profile, parse.parser_version,
                parse.result_sha256, content,
            )
        except GlobalStandardProofError:
            raise
        except RuntimeLicenseError:
            raise GlobalStandardProofError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalStandardProofError() from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Parser result field")
        result[key] = value
    return result
