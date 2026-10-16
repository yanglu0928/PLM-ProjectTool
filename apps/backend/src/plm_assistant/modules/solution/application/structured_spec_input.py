"""Bounded SOL-06 immutable draft input; no source or authorization proof."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.solution.application.structured_spec_payload import (
    StructuredSpecPayloadError,
    ValidatedStructuredSpecPayload,
    validate_structured_spec_payload,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)


class StructuredSpecInputError(RuntimeError):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SpecRequirementRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SpecSectionRef:
    solution_section_id: uuid.UUID
    solution_section_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class StructuredSpecDraftInput:
    project_id: uuid.UUID
    spec_series_id: uuid.UUID | None
    supersedes_version_ref: uuid.UUID | None
    spec_type: str
    payload: object = field(repr=False)
    requirement_refs: tuple[SpecRequirementRef, ...] = ()
    section_refs: tuple[SpecSectionRef, ...] = ()
    evidence_ids: tuple[uuid.UUID, ...] = ()
    artifact_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidatedStructuredSpecDraft:
    project_id: uuid.UUID
    spec_series_id: uuid.UUID | None
    supersedes_version_ref: uuid.UUID | None
    spec_type: str
    payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[SpecRequirementRef, ...] = ()
    section_refs: tuple[SpecSectionRef, ...] = ()
    evidence_ids: tuple[uuid.UUID, ...] = ()
    artifact_ids: tuple[uuid.UUID, ...] = ()
    request_fingerprint: bytes = field(default=b"", repr=False)

    def payload(self) -> dict[str, object]:
        return json.loads(self.payload_json)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _refs(value: object, kind: type, identity_field: str, version_field: str,
          *, minimum: int = 0) -> None:
    if type(value) is not tuple or not minimum <= len(value) <= 500:
        raise StructuredSpecInputError()
    for item in value:
        if (type(item) is not kind or not _id(getattr(item, identity_field))
                or not _id(getattr(item, version_field))):
            raise StructuredSpecInputError()
    if (len({getattr(item, identity_field) for item in value}) != len(value)
            or len({getattr(item, version_field) for item in value}) != len(value)):
        raise StructuredSpecInputError()


def _ids(value: object) -> None:
    if (type(value) is not tuple or len(value) > 500
            or any(not _id(item) for item in value)
            or len(set(value)) != len(value)):
        raise StructuredSpecInputError()


def validate_structured_spec_draft(value: object) -> ValidatedStructuredSpecDraft:
    """Normalize one draft request; current referenced versions remain unproven."""
    if (type(value) is not StructuredSpecDraftInput
            or not _id(value.project_id)
            or (value.spec_series_id is None) != (value.supersedes_version_ref is None)
            or (value.spec_series_id is not None and not _id(value.spec_series_id))
            or (value.supersedes_version_ref is not None
                and not _id(value.supersedes_version_ref))):
        raise StructuredSpecInputError()
    _refs(value.requirement_refs, SpecRequirementRef,
          "requirement_id", "requirement_version_id", minimum=1)
    _refs(value.section_refs, SpecSectionRef,
          "solution_section_id", "solution_section_version_id", minimum=1)
    _ids(value.evidence_ids)
    _ids(value.artifact_ids)
    try:
        payload: ValidatedStructuredSpecPayload = validate_structured_spec_payload(
            value.spec_type, value.payload)
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(value.project_id),
            "spec_series_id": str(value.spec_series_id) if value.spec_series_id else None,
            "supersedes_version_ref": (
                str(value.supersedes_version_ref) if value.supersedes_version_ref else None),
            "spec_type": payload.spec_type,
            "schema_version": payload.schema_version,
            "payload_fingerprint": payload.payload_fingerprint.hex(),
            "requirement_refs": [
                [str(ref.requirement_id), str(ref.requirement_version_id)]
                for ref in value.requirement_refs],
            "section_refs": [
                [str(ref.solution_section_id), str(ref.solution_section_version_id)]
                for ref in value.section_refs],
            "evidence_ids": [str(ref) for ref in value.evidence_ids],
            "artifact_ids": [str(ref) for ref in value.artifact_ids],
        })
    except (StructuredSpecPayloadError, IdempotencyError):
        raise StructuredSpecInputError() from None
    return ValidatedStructuredSpecDraft(
        project_id=value.project_id,
        spec_series_id=value.spec_series_id,
        supersedes_version_ref=value.supersedes_version_ref,
        spec_type=payload.spec_type,
        payload_json=payload.payload_json,
        payload_fingerprint=payload.payload_fingerprint,
        requirement_refs=value.requirement_refs,
        section_refs=value.section_refs,
        evidence_ids=value.evidence_ids,
        artifact_ids=value.artifact_ids,
        request_fingerprint=fingerprint,
    )
