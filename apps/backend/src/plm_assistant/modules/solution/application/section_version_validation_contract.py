"""Fail-closed command and first-result contract for SectionVersion VALIDATE.

No current-fact check is performed here. Only the authorized, same-transaction
Owner may construct facts from trusted repositories and commit the audit/receipt.
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


OPERATION = "V1_SOL_SECTION_VERSION_VALIDATE"
AUDIT_ACTION = "SOL_SECTION_VERSION_VALIDATED"
ValidationStatus = Literal["PASS", "FAIL", "UNAVAILABLE"]
_STATUSES = frozenset(("PASS", "FAIL", "UNAVAILABLE"))
_STATES = frozenset(("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"))
_DIMENSIONS = ("integrity", "content", "requirements", "evidence", "trace", "spec")
_ISSUE_NAMES = {
    "integrity": "FIXED_VERSION",
    "content": "CONTENT_SOURCE",
    "requirements": "REQUIREMENT_SOURCE",
    "evidence": "EVIDENCE_SOURCE",
    "trace": "TRACE_COVERAGE",
    "spec": "STRUCTURED_SPEC",
}
_AUDIT_REASON_PREFIX = "SECTION_VALIDATION_V1_"
_STATUS_TO_LETTER = {"PASS": "P", "FAIL": "F", "UNAVAILABLE": "U"}
_LETTER_TO_STATUS = {letter: status for status, letter in _STATUS_TO_LETTER.items()}


class SectionVersionValidationContractError(ValueError):
    """Malformed command, snapshot, facts or report; never a business PASS."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _aware(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class ValidateSectionVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    solution_section_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or type(self.csrf_token) is not bytes or len(self.csrf_token) != 32
                or not all(_id(value) for value in (self.trace_id, self.project_id,
                                                    self.solution_section_id,
                                                    self.solution_section_version_id))):
            raise SectionVersionValidationContractError("invalid validate command")
        try:
            validate_idempotency_key(self.idempotency_key)
        except IdempotencyError:
            raise SectionVersionValidationContractError("invalid validate key") from None

    def request_fingerprint(self) -> bytes:
        """Stable identity only; current facts belong to the first audited result."""
        return canonical_payload_fingerprint({
            "project_id": str(self.project_id),
            "solution_section_id": str(self.solution_section_id),
            "solution_section_version_id": str(self.solution_section_version_id),
        })

    def scope(self, actor_id: uuid.UUID) -> IdempotencyScope:
        return IdempotencyScope.from_key(
            actor_id=actor_id, project_id=self.project_id,
            operation=OPERATION, key=self.idempotency_key)


@dataclass(frozen=True, slots=True)
class SectionCurrentFactQuery:
    """Internal current-fact identity; carries no VALIDATE receipt or audit key."""

    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    solution_section_version_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.solution_section_id,
                    self.solution_section_version_id))):
            raise SectionVersionValidationContractError("invalid current fact query")


@dataclass(frozen=True, slots=True)
class SectionVersionValidationSnapshot:
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    solution_section_version_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    requirement_count: int
    evidence_count: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (self.project_id, self.solution_section_id,
                                            self.solution_section_version_id))
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.version_state) is not str or self.version_state not in _STATES
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.requirement_count) is not int
                or not 0 <= self.requirement_count <= 500
                or type(self.evidence_count) is not int
                or not 0 <= self.evidence_count <= 500):
            raise SectionVersionValidationContractError("invalid fixed section snapshot")


@dataclass(frozen=True, slots=True)
class SectionVersionValidationFacts:
    integrity: ValidationStatus = "UNAVAILABLE"
    content: ValidationStatus = "UNAVAILABLE"
    requirements: ValidationStatus = "UNAVAILABLE"
    evidence: ValidationStatus = "UNAVAILABLE"
    trace: ValidationStatus = "UNAVAILABLE"
    spec: ValidationStatus = "UNAVAILABLE"

    def __post_init__(self) -> None:
        if any(type(getattr(self, name)) is not str
               or getattr(self, name) not in _STATUSES for name in _DIMENSIONS):
            raise SectionVersionValidationContractError("invalid validation proof state")


def audit_reason_for_facts(facts: SectionVersionValidationFacts) -> str:
    """Bounded first-observation summary for append-only Audit and replay."""
    if type(facts) is not SectionVersionValidationFacts:
        raise SectionVersionValidationContractError("invalid validation facts")
    return _AUDIT_REASON_PREFIX + "".join(
        _STATUS_TO_LETTER[getattr(facts, name)] for name in _DIMENSIONS)


def facts_from_audit_reason(reason: str) -> SectionVersionValidationFacts:
    """Decode only this operation's exact first-result code; never guess PASS."""
    if (type(reason) is not str or not reason.startswith(_AUDIT_REASON_PREFIX)
            or len(reason) != len(_AUDIT_REASON_PREFIX) + len(_DIMENSIONS)):
        raise SectionVersionValidationContractError("invalid validation audit reason")
    try:
        statuses = (_LETTER_TO_STATUS[letter]
                    for letter in reason[len(_AUDIT_REASON_PREFIX):])
        return SectionVersionValidationFacts(**dict(zip(_DIMENSIONS, statuses, strict=True)))
    except (KeyError, TypeError, ValueError):
        raise SectionVersionValidationContractError("invalid validation audit reason") from None


def _issues(state: str, facts: SectionVersionValidationFacts) -> tuple[str, ...]:
    issues = tuple(f"{_ISSUE_NAMES[name]}_{getattr(facts, name)}"
                   for name in _DIMENSIONS if getattr(facts, name) != "PASS")
    if state != "DRAFT":
        return ("VERSION_NOT_DRAFT", *issues)
    return issues


@dataclass(frozen=True, slots=True)
class SectionVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_section_id: uuid.UUID
    solution_section_version_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    requirement_count: int
    evidence_count: int
    facts: SectionVersionValidationFacts
    valid: bool
    ready_for_review: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        try:
            SectionVersionValidationSnapshot(
                self.project_id, self.solution_section_id, self.solution_section_version_id,
                self.version_no, self.version_state, self.content_fingerprint,
                self.requirement_count, self.evidence_count)
        except SectionVersionValidationContractError:
            raise SectionVersionValidationContractError("invalid validation report") from None
        if (not _id(self.audit_event_id) or not _id(self.trace_id)
                or type(self.facts) is not SectionVersionValidationFacts
                or type(self.valid) is not bool or type(self.ready_for_review) is not bool
                or type(self.issue_codes) is not tuple
                or self.issue_codes != _issues(self.version_state, self.facts)
                or not _aware(self.observed_at)):
            raise SectionVersionValidationContractError("invalid validation report")
        source_valid = all(getattr(self.facts, name) == "PASS"
                           for name in _DIMENSIONS[:4])
        ready = (source_valid and self.version_state == "DRAFT"
                 and self.facts.trace == "PASS" and self.facts.spec == "PASS")
        if self.valid != source_valid or self.ready_for_review != ready:
            raise SectionVersionValidationContractError("invalid validation conclusion")


def build_section_version_validation_report(
    command: ValidateSectionVersion, snapshot: SectionVersionValidationSnapshot,
    facts: SectionVersionValidationFacts, *, audit_event_id: uuid.UUID,
    observed_at: datetime,
) -> SectionVersionValidationReport:
    """Bind a trusted first observation to immutable version identity and audit."""
    if (type(command) is not ValidateSectionVersion
            or type(snapshot) is not SectionVersionValidationSnapshot
            or type(facts) is not SectionVersionValidationFacts
            or (command.project_id, command.solution_section_id,
                command.solution_section_version_id) != (
                    snapshot.project_id, snapshot.solution_section_id,
                    snapshot.solution_section_version_id)):
        raise SectionVersionValidationContractError("validation identity mismatch")
    valid = all(getattr(facts, name) == "PASS" for name in _DIMENSIONS[:4])
    ready = (valid and snapshot.version_state == "DRAFT"
             and facts.trace == "PASS" and facts.spec == "PASS")
    return SectionVersionValidationReport(
        audit_event_id=audit_event_id, trace_id=command.trace_id,
        project_id=snapshot.project_id, solution_section_id=snapshot.solution_section_id,
        solution_section_version_id=snapshot.solution_section_version_id,
        version_no=snapshot.version_no, version_state=snapshot.version_state,
        content_fingerprint=snapshot.content_fingerprint,
        requirement_count=snapshot.requirement_count, evidence_count=snapshot.evidence_count,
        facts=facts, valid=valid, ready_for_review=ready,
        issue_codes=_issues(snapshot.version_state, facts), observed_at=observed_at)
