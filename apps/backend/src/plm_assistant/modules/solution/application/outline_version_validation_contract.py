"""Fail-closed fixed OutlineVersion validation contract; no current proof here.

Only a later authorized Owner may collect order/source/coverage facts in its
transaction. A report records one audited observation, never future approval.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)


OPERATION = "V1_SOL_OUTLINE_VERSION_VALIDATE"
AUDIT_ACTION = "SOL_OUTLINE_VERSION_VALIDATED"
ValidationStatus = Literal["PASS", "FAIL", "UNAVAILABLE"]
_STATUSES = frozenset(("PASS", "FAIL", "UNAVAILABLE"))
_STATES = frozenset(("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"))
_DIMENSIONS = ("order", "source", "coverage")
_ISSUES = {
    "order": "SECTION_ORDER",
    "source": "FIXED_SOURCE",
    "coverage": "REQUIREMENT_COVERAGE",
}
_AUDIT_REASON_PREFIX = "OUTLINE_VALIDATION_V1_"
_STATUS_TO_LETTER = {"PASS": "P", "FAIL": "F", "UNAVAILABLE": "U"}
_LETTER_TO_STATUS = {letter: status for status, letter in _STATUS_TO_LETTER.items()}


class OutlineVersionValidationContractError(ValueError):
    """Malformed command, snapshot, facts or report; never a business PASS."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _aware(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class ValidateOutlineVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_outline_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or type(self.csrf_token) is not bytes or len(self.csrf_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.solution_outline_id,
                    self.solution_outline_version_id))):
            raise OutlineVersionValidationContractError("invalid validate command")
        try:
            validate_idempotency_key(self.idempotency_key)
        except IdempotencyError:
            raise OutlineVersionValidationContractError("invalid validate key") from None

    def request_fingerprint(self) -> bytes:
        """Stable request identity; current facts belong to the first observation."""
        return canonical_payload_fingerprint({
            "project_id": str(self.project_id),
            "solution_outline_id": str(self.solution_outline_id),
            "solution_outline_version_id": str(self.solution_outline_version_id),
        })

    def scope(self, actor_id: uuid.UUID) -> IdempotencyScope:
        return IdempotencyScope.from_key(
            actor_id=actor_id, project_id=self.project_id,
            operation=OPERATION, key=self.idempotency_key)


@dataclass(frozen=True, slots=True)
class OutlineCurrentFactQuery:
    """Internal Review reproof identity; caller owns authorization and transaction."""

    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_outline_version_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.solution_outline_id,
                    self.solution_outline_version_id))):
            raise OutlineVersionValidationContractError(
                "invalid current Outline query")


@dataclass(frozen=True, slots=True)
class OutlineVersionValidationSnapshot:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_outline_version_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    section_count: int
    requirement_count: int
    reference_count: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.project_id, self.solution_outline_id,
                self.solution_outline_version_id))
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.version_state) is not str or self.version_state not in _STATES
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.section_count) is not int
                or not 1 <= self.section_count <= 100
                or type(self.requirement_count) is not int
                or not 0 <= self.requirement_count <= 500
                or type(self.reference_count) is not int
                or not 0 <= self.reference_count <= 500):
            raise OutlineVersionValidationContractError("invalid fixed outline snapshot")


@dataclass(frozen=True, slots=True)
class OutlineVersionValidationFacts:
    order: ValidationStatus = "UNAVAILABLE"
    source: ValidationStatus = "UNAVAILABLE"
    coverage: ValidationStatus = "UNAVAILABLE"

    def __post_init__(self) -> None:
        if any(type(getattr(self, name)) is not str
               or getattr(self, name) not in _STATUSES for name in _DIMENSIONS):
            raise OutlineVersionValidationContractError("invalid validation proof state")


def audit_reason_for_facts(facts: OutlineVersionValidationFacts) -> str:
    """Bounded, content-free first-observation summary for Audit replay."""
    if type(facts) is not OutlineVersionValidationFacts:
        raise OutlineVersionValidationContractError("invalid validation facts")
    return _AUDIT_REASON_PREFIX + "".join(
        _STATUS_TO_LETTER[getattr(facts, name)] for name in _DIMENSIONS)


def facts_from_audit_reason(reason: str) -> OutlineVersionValidationFacts:
    """Decode only this operation's exact result; never infer PASS."""
    if (type(reason) is not str or not reason.startswith(_AUDIT_REASON_PREFIX)
            or len(reason) != len(_AUDIT_REASON_PREFIX) + len(_DIMENSIONS)):
        raise OutlineVersionValidationContractError("invalid validation audit reason")
    try:
        statuses = (_LETTER_TO_STATUS[letter]
                    for letter in reason[len(_AUDIT_REASON_PREFIX):])
        return OutlineVersionValidationFacts(**dict(zip(_DIMENSIONS, statuses, strict=True)))
    except (KeyError, TypeError, ValueError):
        raise OutlineVersionValidationContractError("invalid validation audit reason") from None


def _issues(state: str, facts: OutlineVersionValidationFacts) -> tuple[str, ...]:
    issues = tuple(f"{_ISSUES[name]}_{getattr(facts, name)}"
                   for name in _DIMENSIONS if getattr(facts, name) != "PASS")
    return issues if state == "DRAFT" else ("VERSION_NOT_DRAFT", *issues)


@dataclass(frozen=True, slots=True)
class OutlineVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_outline_version_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    section_count: int
    requirement_count: int
    reference_count: int
    facts: OutlineVersionValidationFacts
    valid: bool
    ready_for_review: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        try:
            OutlineVersionValidationSnapshot(
                self.project_id, self.solution_outline_id,
                self.solution_outline_version_id, self.version_no,
                self.version_state, self.content_fingerprint,
                self.section_count, self.requirement_count, self.reference_count)
        except OutlineVersionValidationContractError:
            raise OutlineVersionValidationContractError("invalid validation report") from None
        if (not _id(self.audit_event_id) or not _id(self.trace_id)
                or type(self.facts) is not OutlineVersionValidationFacts
                or type(self.valid) is not bool
                or type(self.ready_for_review) is not bool
                or type(self.issue_codes) is not tuple
                or self.issue_codes != _issues(self.version_state, self.facts)
                or not _aware(self.observed_at)):
            raise OutlineVersionValidationContractError("invalid validation report")
        valid = all(getattr(self.facts, name) == "PASS" for name in _DIMENSIONS)
        if (self.valid != valid
                or self.ready_for_review != (valid and self.version_state == "DRAFT")):
            raise OutlineVersionValidationContractError("invalid validation conclusion")


def build_outline_version_validation_report(
    command: ValidateOutlineVersion,
    snapshot: OutlineVersionValidationSnapshot,
    facts: OutlineVersionValidationFacts,
    *, audit_event_id: uuid.UUID, observed_at: datetime,
) -> OutlineVersionValidationReport:
    """Bind trusted first-observation facts to fixed identity and audit."""
    if (type(command) is not ValidateOutlineVersion
            or type(snapshot) is not OutlineVersionValidationSnapshot
            or type(facts) is not OutlineVersionValidationFacts
            or (command.project_id, command.solution_outline_id,
                command.solution_outline_version_id) != (
                    snapshot.project_id, snapshot.solution_outline_id,
                    snapshot.solution_outline_version_id)):
        raise OutlineVersionValidationContractError("validation identity mismatch")
    valid = all(getattr(facts, name) == "PASS" for name in _DIMENSIONS)
    return OutlineVersionValidationReport(
        audit_event_id=audit_event_id, trace_id=command.trace_id,
        project_id=snapshot.project_id,
        solution_outline_id=snapshot.solution_outline_id,
        solution_outline_version_id=snapshot.solution_outline_version_id,
        version_no=snapshot.version_no, version_state=snapshot.version_state,
        content_fingerprint=snapshot.content_fingerprint,
        section_count=snapshot.section_count,
        requirement_count=snapshot.requirement_count,
        reference_count=snapshot.reference_count, facts=facts,
        valid=valid, ready_for_review=valid and snapshot.version_state == "DRAFT",
        issue_codes=_issues(snapshot.version_state, facts), observed_at=observed_at)
