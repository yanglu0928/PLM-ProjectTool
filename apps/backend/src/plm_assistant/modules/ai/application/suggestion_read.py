"""Authorized, canonical Suggestion read with current Document-owned locators."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.invocation_read import AIInvocationContextView
from plm_assistant.modules.ai.application.output_schema import (
    AIOutputSchemaError,
    AIOutputSchemaRegistry,
)
from plm_assistant.modules.ai.application.task_read import AITaskInputView
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocationError,
    DocumentNodeLocationService,
    DocumentVersionLocationService,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z")
_QUALITY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_MANAGEMENT_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class AISuggestionReadError(RuntimeError):
    def __init__(self, code: str = "AI_SUGGESTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _time(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class GetAISuggestion:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    ai_task_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.ai_task_id))):
            raise AISuggestionReadError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AISuggestionEvidenceFact:
    ref_ordinal: int
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    content_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.ref_ordinal) is not int or not 1 <= self.ref_ordinal <= 256
                or self.owner_module != "document"
                or self.object_type != "DOCUMENT_VERSION"
                or not _id(self.object_id) or not _id(self.version_id)
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32):
            raise AISuggestionReadError()


@dataclass(frozen=True, slots=True)
class AISuggestionSourceFact:
    source_ordinal: int
    resource_type: str
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID
    content_revision_id: uuid.UUID
    content_object_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    content_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.source_ordinal) is not int
                or not 1 <= self.source_ordinal <= 1000
                or self.resource_type != "DOC-02"
                or self.owner_module != "document"
                or self.object_type != "DOCUMENT_VERSION"
                or not all(_id(value) for value in (
                    self.object_id, self.version_id, self.project_id,
                    self.content_revision_id, self.content_object_id))
                or any(type(value) is not bytes or len(value) != 32 for value in (
                    self.source_fingerprint, self.content_fingerprint))):
            raise AISuggestionReadError()


@dataclass(frozen=True, slots=True)
class AISuggestionReadRecord:
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    task_state: str
    suggestion_state: str
    task_lock_version: int
    ai_invocation_id: uuid.UUID
    suggestion_payload_id: uuid.UUID
    content_plan_id: uuid.UUID
    input_versions: tuple[AITaskInputView, ...]
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    model_revision: str
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    output_schema_ref: str
    schema_version: int
    context: AIInvocationContextView
    canonical_payload: object = field(repr=False)
    canonical_payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    fact_status: str
    quality_flags: tuple[str, ...]
    created_at: datetime
    evidence: tuple[AISuggestionEvidenceFact, ...]
    sources: tuple[AISuggestionSourceFact, ...]

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.ai_task_id, self.project_id, self.requested_by,
                self.ai_invocation_id, self.suggestion_payload_id,
                self.content_plan_id, self.ai_provider_id,
                self.provider_config_version_id, self.ai_model_id,
                self.prompt_template_id))
                or self.task_state != "SUCCEEDED"
                or self.suggestion_state not in {
                    "AVAILABLE", "ACCEPTED_TO_DRAFT", "REJECTED", "SUPERSEDED"}
                or type(self.task_lock_version) is not int
                or self.task_lock_version < 0
                or type(self.input_versions) is not tuple
                or not self.input_versions
                or any(type(value) is not AITaskInputView
                       for value in self.input_versions)
                or any(value.resource_type != "DOC-02"
                       or not _id(value.resource_id) or not _id(value.version_id)
                       for value in self.input_versions)
                or type(self.model_revision) is not str
                or not self.model_revision or len(self.model_revision) > 128
                or type(self.prompt_version_no) is not int
                or self.prompt_version_no < 1
                or type(self.output_schema_ref) is not str
                or _REF.fullmatch(self.output_schema_ref) is None
                or type(self.schema_version) is not int or self.schema_version < 1
                or type(self.context) is not AIInvocationContextView
                or type(self.canonical_payload_json) is not bytes
                or not 2 <= len(self.canonical_payload_json) <= 1_048_576
                or type(self.payload_fingerprint) is not bytes
                or len(self.payload_fingerprint) != 32
                or self.fact_status != "NOT_FORMAL_FACT"
                or type(self.quality_flags) is not tuple
                or len(self.quality_flags) > 64
                or any(type(value) is not str or _QUALITY.fullmatch(value) is None
                       for value in self.quality_flags)
                or tuple(sorted(set(self.quality_flags))) != self.quality_flags
                or not _time(self.created_at)
                or type(self.evidence) is not tuple or not self.evidence
                or type(self.sources) is not tuple or not self.sources):
            raise AISuggestionReadError()
        self.context.__post_init__()
        for value in self.evidence + self.sources:
            value.__post_init__()


@dataclass(frozen=True, slots=True)
class AISuggestionSourceLocationView:
    source_ordinal: int
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    precision: str
    content_url: str
    locations: tuple[dict[str, object], ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.source_ordinal) is not int
                or not 1 <= self.source_ordinal <= 1000
                or not _id(self.document_id) or not _id(self.document_version_id)
                or self.precision not in {"DOCUMENT", "PARSED_NODE"}
                or type(self.content_url) is not str
                or not self.content_url.startswith("/api/v1/")
                or type(self.locations) is not tuple or not self.locations
                or any(type(value) is not dict for value in self.locations)):
            raise AISuggestionReadError()


@dataclass(frozen=True, slots=True)
class AISuggestionView:
    record: AISuggestionReadRecord
    locations: tuple[AISuggestionSourceLocationView, ...]

    def __post_init__(self) -> None:
        if type(self.record) is not AISuggestionReadRecord:
            raise AISuggestionReadError()
        self.record.__post_init__()
        if (type(self.locations) is not tuple or not self.locations
                or any(type(value) is not AISuggestionSourceLocationView
                       for value in self.locations)
                or tuple(item.source_ordinal for item in self.locations)
                != tuple(sorted(item.source_ordinal for item in self.locations))):
            raise AISuggestionReadError()
        for value in self.locations:
            value.__post_init__()


class AISuggestionReadRepositoryPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            ai_task_id: uuid.UUID) -> AISuggestionReadRecord | None: ...


class AISuggestionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: AISuggestionReadRepositoryPort,
                 schemas: AIOutputSchemaRegistry,
                 document_nodes: DocumentNodeLocationService,
                 document_versions: DocumentVersionLocationService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository,
            schemas, document_nodes, document_versions,
        )):
            raise ValueError("AI Suggestion read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._schemas, self._nodes, self._versions = (
            schemas, document_nodes, document_versions,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: GetAISuggestion) -> AISuggestionView:
        if type(query) is not GetAISuggestion:
            raise AISuggestionReadError("VALIDATION_FAILED")
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            actor, role, record = self._load_authorized(query)
            schema = self._schemas.resolve(
                record.output_schema_ref, record.schema_version,
            )
            ordinals, nodes = _declared_sources(
                record.canonical_payload, record.schema_version,
            )
            validated = schema.validate(
                record.canonical_payload,
                allowed_source_ordinals=frozenset(ordinals),
                allowed_source_nodes=({key: frozenset(value)
                                       for key, value in nodes.items()}
                                      if nodes else None),
            )
            if (validated.canonical_json != record.canonical_payload_json
                    or not hmac.compare_digest(
                        hashlib.sha256(validated.canonical_json).digest(),
                        record.payload_fingerprint)
                    or validated.evidence_ordinals != ordinals):
                raise AISuggestionReadError()
            source_map = _validate_evidence(record, ordinals)
            locations = self._resolve_locations(query, record, source_map, nodes)
            self._guard.require_valid(trace_id=query.trace_id)
            actor2, role2, current = self._load_authorized(query)
            if actor2 != actor or role2 != role or current != record:
                raise AISuggestionReadError("RESOURCE_NOT_FOUND")
            self._guard.require_valid(trace_id=query.trace_id)
            return AISuggestionView(record, locations)
        except AISuggestionReadError:
            raise
        except (AIOutputSchemaError, DocumentNodeLocationError):
            raise AISuggestionReadError("RESOURCE_NOT_FOUND") from None
        except ProjectAuthorizationError:
            raise AISuggestionReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AISuggestionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AISuggestionReadError() from None

    def _load_authorized(
        self, query: GetAISuggestion,
    ) -> tuple[uuid.UUID, str, AISuggestionReadRecord]:
        with self._uow() as transaction:
            now = self._clock()
            if not _time(now):
                raise AISuggestionReadError()
            actor = self._access.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if not _id(actor):
                raise AISuggestionReadError("AUTH_ACCESS_DENIED")
            proof = self._authorization.require_in_transaction(
                transaction, user_id=actor, project_id=query.project_id,
                operation="AI_TASK_SUGGESTION_GET",
            )
            if (type(proof) is not AuthorizedProjectAction
                    or proof.user_id != actor or proof.project_id != query.project_id
                    or proof.operation != "AI_TASK_SUGGESTION_GET"
                    or proof.project_role not in {
                        "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                        "CUSTOMER_MANAGER"}):
                raise AISuggestionReadError("RESOURCE_NOT_FOUND")
            record = self._repository.get(
                transaction, project_id=query.project_id,
                ai_task_id=query.ai_task_id,
            )
            if (type(record) is not AISuggestionReadRecord
                    or record.requested_by != actor
                    and proof.project_role not in _MANAGEMENT_ROLES):
                raise AISuggestionReadError("RESOURCE_NOT_FOUND")
            record.__post_init__()
            return actor, proof.project_role, record

    def _resolve_locations(
        self, query: GetAISuggestion,
        record: AISuggestionReadRecord,
        sources: dict[int, AISuggestionSourceFact],
        nodes: dict[int, tuple[str, ...]],
    ) -> tuple[AISuggestionSourceLocationView, ...]:
        document_query = DocumentReadQuery(
            query.session_token, query.trace_id, "PROJECT", query.project_id,
        )
        all_sources = {
            (item.object_id, item.version_id): item for item in record.sources
        }
        input_ids = tuple(
            (item.resource_id, item.version_id) for item in record.input_versions
        )
        if (len(all_sources) != len(record.sources)
                or len(set(input_ids)) != len(input_ids)
                or set(input_ids) != set(all_sources)):
            raise AISuggestionReadError("RESOURCE_NOT_FOUND")
        current_versions = {}
        for identity in input_ids:
            current = self._versions.resolve(
                document_query, document_id=identity[0],
                document_version_id=identity[1],
            )
            if not hmac.compare_digest(
                    current.source_sha256, all_sources[identity].source_fingerprint):
                raise AISuggestionReadError("RESOURCE_NOT_FOUND")
            current_versions[identity] = current
        result: list[AISuggestionSourceLocationView] = []
        for ordinal, source in sorted(sources.items()):
            if nodes:
                resolved = self._nodes.resolve(
                    document_query, document_id=source.object_id,
                    document_version_id=source.version_id,
                    parse_record_id=source.content_revision_id,
                    node_ids=nodes[ordinal],
                )
                if (resolved.result_ref_id != source.content_object_id
                        or not hmac.compare_digest(
                            resolved.source_sha256, source.source_fingerprint)
                        or not hmac.compare_digest(
                            resolved.result_sha256, source.content_fingerprint)):
                    raise AISuggestionReadError("RESOURCE_NOT_FOUND")
                values = tuple({
                    "node_id": item.node_id,
                    "kind": item.kind,
                    "locator": item.locator,
                    "precision": item.precision,
                    "display_label": item.display_label,
                } for item in resolved.locations)
                result.append(AISuggestionSourceLocationView(
                    ordinal, source.object_id, source.version_id,
                    "PARSED_NODE", resolved.content_url, values,
                ))
            else:
                resolved = current_versions[(source.object_id, source.version_id)]
                result.append(AISuggestionSourceLocationView(
                    ordinal, source.object_id, source.version_id,
                    "DOCUMENT", resolved.content_url, ({
                        "locator": resolved.locator,
                        "precision": resolved.precision,
                        "display_label": resolved.display_label,
                    },),
                ))
        return tuple(result)


def _declared_sources(
    payload: object, schema_version: int,
) -> tuple[tuple[int, ...], dict[int, tuple[str, ...]]]:
    if type(payload) is not dict or type(payload.get("items")) is not list:
        raise AISuggestionReadError()
    ordinals: set[int] = set()
    node_map: dict[int, set[str]] = {}
    if schema_version == 1:
        for item in payload["items"]:
            if type(item) is not dict or type(item.get("source_ordinals")) is not list:
                raise AISuggestionReadError()
            ordinals.update(item["source_ordinals"])
    elif schema_version == 2:
        for item in payload["items"]:
            if type(item) is not dict or type(item.get("source_citations")) is not list:
                raise AISuggestionReadError()
            for citation in item["source_citations"]:
                if (type(citation) is not dict
                        or type(citation.get("source_ordinal")) is not int
                        or type(citation.get("node_ids")) is not list):
                    raise AISuggestionReadError()
                ordinal = citation["source_ordinal"]
                ordinals.add(ordinal)
                node_map.setdefault(ordinal, set()).update(citation["node_ids"])
    else:
        raise AISuggestionReadError()
    if (not ordinals or any(type(value) is not int or not 1 <= value <= 1000
                            for value in ordinals)):
        raise AISuggestionReadError()
    return (tuple(sorted(ordinals)),
            {key: tuple(sorted(value)) for key, value in sorted(node_map.items())})


def _validate_evidence(
    record: AISuggestionReadRecord, ordinals: tuple[int, ...],
) -> dict[int, AISuggestionSourceFact]:
    source_map = {value.source_ordinal: value for value in record.sources}
    if (len(source_map) != len(record.sources)
            or tuple(item.ref_ordinal for item in record.evidence)
            != tuple(range(1, len(record.evidence) + 1))
            or len(record.evidence) != len(ordinals)):
        raise AISuggestionReadError()
    selected: dict[int, AISuggestionSourceFact] = {}
    for evidence, ordinal in zip(record.evidence, ordinals, strict=True):
        source = source_map.get(ordinal)
        if (source is None or source.project_id != record.project_id
                or (evidence.owner_module, evidence.object_type,
                    evidence.object_id, evidence.version_id)
                != (source.owner_module, source.object_type,
                    source.object_id, source.version_id)
                or not hmac.compare_digest(
                    evidence.content_fingerprint, source.content_fingerprint)):
            raise AISuggestionReadError()
        selected[ordinal] = source
    return selected
