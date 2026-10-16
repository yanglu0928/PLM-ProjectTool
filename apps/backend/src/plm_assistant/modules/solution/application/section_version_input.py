"""Bounded SectionVersion DRAFT input; no source or authorization proof."""

from __future__ import annotations

import json
import unicodedata
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)


class SectionVersionInputError(RuntimeError):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SectionRequirementRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SectionVersionDraftInput:
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    title: str
    content_document_version_ref: uuid.UUID | None
    content_artifact_ref: uuid.UUID | None
    requirement_refs: tuple[SectionRequirementRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    assumptions: tuple[dict[str, object], ...] = field(repr=False)
    exclusions: tuple[dict[str, object], ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ValidatedSectionVersionDraft:
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    title: str
    content_document_version_ref: uuid.UUID | None
    content_artifact_ref: uuid.UUID | None
    requirement_refs: tuple[SectionRequirementRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    assumptions_json: bytes = field(repr=False)
    exclusions_json: bytes = field(repr=False)
    request_fingerprint: bytes = field(repr=False)

    def assumptions(self) -> list[dict[str, object]]:
        return json.loads(self.assumptions_json)

    def exclusions(self) -> list[dict[str, object]]:
        return json.loads(self.exclusions_json)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _json_keys_are_strings(value: object) -> bool:
    if type(value) is dict:
        return all(type(key) is str and _json_keys_are_strings(item)
                   for key, item in value.items())
    if type(value) in (list, tuple):
        return all(_json_keys_are_strings(item) for item in value)
    return True


def _declarations(value: object) -> tuple[bytes, list[dict[str, object]]]:
    if type(value) is not tuple or len(value) > 100:
        raise SectionVersionInputError()
    try:
        if any(type(item) is not dict or not _json_keys_are_strings(item)
               for item in value):
            raise SectionVersionInputError()
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 64_000:
            raise SectionVersionInputError()
        copied = json.loads(encoded)
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        raise SectionVersionInputError() from None
    return encoded, copied


def validate_section_version_draft(value: object) -> ValidatedSectionVersionDraft:
    if (type(value) is not SectionVersionDraftInput
            or not _id(value.project_id) or not _id(value.solution_section_id)
            or type(value.title) is not str
            or not 1 <= len(value.title) <= 500
            or value.title != value.title.strip()
            or value.title != unicodedata.normalize("NFC", value.title)
            or any(unicodedata.category(char) in ("Cc", "Cs") for char in value.title)
            or (value.content_document_version_ref is not None
                and not _id(value.content_document_version_ref))
            or (value.content_artifact_ref is not None
                and not _id(value.content_artifact_ref))
            or ((value.content_document_version_ref is None)
                == (value.content_artifact_ref is None))
            or type(value.requirement_refs) is not tuple
            or len(value.requirement_refs) > 500
            or type(value.evidence_ids) is not tuple
            or len(value.evidence_ids) > 500):
        raise SectionVersionInputError()
    for item in value.requirement_refs:
        if (type(item) is not SectionRequirementRef
                or not _id(item.requirement_id)
                or not _id(item.requirement_version_id)):
            raise SectionVersionInputError()
    if (len({item.requirement_id for item in value.requirement_refs})
            != len(value.requirement_refs)
            or len({item.requirement_version_id for item in value.requirement_refs})
            != len(value.requirement_refs)
            or any(not _id(item) for item in value.evidence_ids)
            or len(set(value.evidence_ids)) != len(value.evidence_ids)):
        raise SectionVersionInputError()
    assumptions_json, assumptions = _declarations(value.assumptions)
    exclusions_json, exclusions = _declarations(value.exclusions)
    try:
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(value.project_id),
            "solution_section_id": str(value.solution_section_id),
            "title": value.title,
            "content_document_version_ref": (
                str(value.content_document_version_ref)
                if value.content_document_version_ref is not None else None),
            "content_artifact_ref": (
                str(value.content_artifact_ref)
                if value.content_artifact_ref is not None else None),
            "requirement_refs": [
                [str(item.requirement_id), str(item.requirement_version_id)]
                for item in value.requirement_refs],
            "evidence_ids": [str(item) for item in value.evidence_ids],
            "assumptions": assumptions,
            "exclusions": exclusions,
        })
    except IdempotencyError:
        raise SectionVersionInputError() from None
    return ValidatedSectionVersionDraft(
        value.project_id, value.solution_section_id, value.title,
        value.content_document_version_ref, value.content_artifact_ref,
        value.requirement_refs, value.evidence_ids,
        assumptions_json, exclusions_json, fingerprint)
