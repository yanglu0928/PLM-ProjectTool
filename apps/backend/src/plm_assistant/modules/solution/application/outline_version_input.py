"""Frozen OutlineVersion DRAFT input normalization, before any database write."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)


class OutlineVersionInputError(RuntimeError):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineRequirementRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutlineReferenceRef:
    scope: str
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutlineVersionDraftInput:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    section_ids: tuple[uuid.UUID, ...]
    requirement_refs: tuple[OutlineRequirementRef, ...]
    reference_refs: tuple[OutlineReferenceRef, ...]
    missing_declarations: tuple[dict[str, object], ...] = field(repr=False)
    conflict_declarations: tuple[dict[str, object], ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ValidatedOutlineVersionDraft:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    section_ids: tuple[uuid.UUID, ...]
    requirement_refs: tuple[OutlineRequirementRef, ...]
    reference_refs: tuple[OutlineReferenceRef, ...]
    missing_json: bytes = field(repr=False)
    conflict_json: bytes = field(repr=False)
    request_fingerprint: bytes = field(repr=False)

    def missing_declarations(self) -> list[dict[str, object]]:
        return json.loads(self.missing_json)

    def conflict_declarations(self) -> list[dict[str, object]]:
        return json.loads(self.conflict_json)


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
        raise OutlineVersionInputError()
    try:
        if any(type(item) is not dict or not _json_keys_are_strings(item)
               for item in value):
            raise OutlineVersionInputError()
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 64_000:
            raise OutlineVersionInputError()
        copied = json.loads(encoded)
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        raise OutlineVersionInputError() from None
    return encoded, copied


def validate_outline_version_draft(value: object) -> ValidatedOutlineVersionDraft:
    if (type(value) is not OutlineVersionDraftInput
            or not _id(value.project_id) or not _id(value.solution_outline_id)
            or type(value.section_ids) is not tuple
            or not 1 <= len(value.section_ids) <= 100
            or any(not _id(item) for item in value.section_ids)
            or len(set(value.section_ids)) != len(value.section_ids)
            or type(value.requirement_refs) is not tuple
            or len(value.requirement_refs) > 500
            or type(value.reference_refs) is not tuple
            or len(value.reference_refs) > 500):
        raise OutlineVersionInputError()
    for item in value.requirement_refs:
        if (type(item) is not OutlineRequirementRef
                or not _id(item.requirement_id)
                or not _id(item.requirement_version_id)):
            raise OutlineVersionInputError()
    if (len({item.requirement_id for item in value.requirement_refs})
            != len(value.requirement_refs)
            or len({item.requirement_version_id for item in value.requirement_refs})
            != len(value.requirement_refs)):
        raise OutlineVersionInputError()
    for item in value.reference_refs:
        if (type(item) is not OutlineReferenceRef
                or item.scope not in ("PROJECT", "GLOBAL")
                or not _id(item.reference_solution_id)
                or not _id(item.reference_version_id)):
            raise OutlineVersionInputError()
    if (len({item.reference_solution_id for item in value.reference_refs})
            != len(value.reference_refs)
            or len({item.reference_version_id for item in value.reference_refs})
            != len(value.reference_refs)):
        raise OutlineVersionInputError()
    missing_json, missing = _declarations(value.missing_declarations)
    conflict_json, conflict = _declarations(value.conflict_declarations)
    if not value.requirement_refs and not value.reference_refs and not missing:
        raise OutlineVersionInputError()
    try:
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(value.project_id),
            "solution_outline_id": str(value.solution_outline_id),
            "section_ids": [str(item) for item in value.section_ids],
            "requirement_refs": [
                [str(item.requirement_id), str(item.requirement_version_id)]
                for item in value.requirement_refs],
            "reference_refs": [
                [item.scope, str(item.reference_solution_id),
                 str(item.reference_version_id)] for item in value.reference_refs],
            "missing_declarations": missing,
            "conflict_declarations": conflict,
        })
    except IdempotencyError:
        raise OutlineVersionInputError() from None
    return ValidatedOutlineVersionDraft(
        value.project_id, value.solution_outline_id, value.section_ids,
        value.requirement_refs, value.reference_refs,
        missing_json, conflict_json, fingerprint)
