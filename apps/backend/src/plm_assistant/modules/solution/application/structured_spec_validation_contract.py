"""Pure first-observation contract for SOL_SPEC_VALIDATE.

This module derives no live facts. Authorized Owners must populate every
dimension and type check; absent proof remains UNAVAILABLE, never PASS.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)


OPERATION = "V1_SOL_STRUCTURED_SPEC_VALIDATE"
AUDIT_ACTION = "SOL_STRUCTURED_SPEC_VALIDATED"
ValidationStatus = Literal["PASS", "FAIL", "UNAVAILABLE"]
_STATUSES = frozenset(("PASS", "FAIL", "UNAVAILABLE"))
_STATES = frozenset(("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                     "SUPERSEDED", "RESTRICTED"))
_DIMENSIONS = ("integrity", "payload", "requirements", "sections", "evidence",
               "artifacts", "trace", "current_version")
_VALID_DIMENSIONS = _DIMENSIONS[:5]
_ISSUE_NAMES = {
    "integrity": "FIXED_VERSION",
    "payload": "PAYLOAD_STRUCTURE",
    "requirements": "REQUIREMENT_SOURCE",
    "sections": "SECTION_SOURCE",
    "evidence": "EVIDENCE_SOURCE",
    "artifacts": "ARTIFACT_SOURCE",
    "trace": "TRACE_COVERAGE",
    "current_version": "CURRENT_VERSION",
}
_TYPE_CHECKS = {
    "PROCESS_MODEL": (
        "GRAPH_STRUCTURE", "ROLE_TRACEABILITY", "INPUT_OUTPUT_TRACEABILITY"),
    "INTERFACE_SPEC": (
        "BOUNDARY_MAPPING", "OWNERSHIP_RUNTIME", "AUTHENTICATION_CONTROL"),
    "MIGRATION_SPEC": (
        "SCOPE_MAPPING", "TRIAL_EXECUTION", "RECONCILIATION_PROOF",
        "ROLLBACK_PROOF", "ACCEPTANCE_PROOF"),
    "PERMISSION_DESIGN": (
        "MATRIX_DEFAULT_DENY", "SCOPE_CONTROL", "DUTY_CONFLICT_REVIEW"),
}
_TYPE_CODES = {
    "PROCESS_MODEL": "PM", "INTERFACE_SPEC": "IF",
    "MIGRATION_SPEC": "MG", "PERMISSION_DESIGN": "PD",
}
_CODE_TYPES = {code: spec_type for spec_type, code in _TYPE_CODES.items()}
_AUDIT_REASON_PREFIX = "SPEC_VALIDATION_V1_"
_STATUS_TO_LETTER = {"PASS": "P", "FAIL": "F", "UNAVAILABLE": "U"}
_LETTER_TO_STATUS = {letter: status for status, letter in _STATUS_TO_LETTER.items()}


class StructuredSpecValidationContractError(ValueError):
    """Malformed command, facts or report; never a business validation result."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _aware(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _status(value: object) -> bool:
    return type(value) is str and value in _STATUSES


@dataclass(frozen=True, slots=True)
class ValidateStructuredSpec:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    structured_solution_spec_id: uuid.UUID
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or type(self.csrf_token) is not bytes or len(self.csrf_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id,
                    self.structured_solution_spec_id))):
            raise StructuredSpecValidationContractError("invalid validate command")
        try:
            validate_idempotency_key(self.idempotency_key)
        except IdempotencyError:
            raise StructuredSpecValidationContractError("invalid validate key") from None

    def request_fingerprint(self) -> bytes:
        return canonical_payload_fingerprint({
            "project_id": str(self.project_id),
            "structured_solution_spec_id": str(self.structured_solution_spec_id),
        })

    def scope(self, actor_id: uuid.UUID) -> IdempotencyScope:
        return IdempotencyScope.from_key(
            actor_id=actor_id, project_id=self.project_id,
            operation=OPERATION, key=self.idempotency_key)


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationSnapshot:
    project_id: uuid.UUID
    structured_solution_spec_id: uuid.UUID
    spec_series_id: uuid.UUID
    spec_type: str
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    requirement_count: int
    section_count: int
    evidence_count: int
    artifact_count: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.project_id, self.structured_solution_spec_id,
                self.spec_series_id))
                or type(self.spec_type) is not str or self.spec_type not in _TYPE_CHECKS
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.version_state) is not str
                or self.version_state not in _STATES
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.payload_fingerprint) is not bytes
                or len(self.payload_fingerprint) != 32
                or any(type(value) is not int for value in (
                    self.requirement_count, self.section_count,
                    self.evidence_count, self.artifact_count))
                or not 1 <= self.requirement_count <= 500
                or not 1 <= self.section_count <= 500
                or not 0 <= self.evidence_count <= 500
                or not 0 <= self.artifact_count <= 500):
            raise StructuredSpecValidationContractError("invalid fixed spec snapshot")


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationFacts:
    integrity: ValidationStatus = "UNAVAILABLE"
    payload: ValidationStatus = "UNAVAILABLE"
    requirements: ValidationStatus = "UNAVAILABLE"
    sections: ValidationStatus = "UNAVAILABLE"
    evidence: ValidationStatus = "UNAVAILABLE"
    artifacts: ValidationStatus = "UNAVAILABLE"
    trace: ValidationStatus = "UNAVAILABLE"
    current_version: ValidationStatus = "UNAVAILABLE"

    def __post_init__(self) -> None:
        if any(not _status(getattr(self, name)) for name in _DIMENSIONS):
            raise StructuredSpecValidationContractError("invalid validation proof state")


@dataclass(frozen=True, slots=True)
class StructuredSpecTypeCheck:
    code: str
    status: ValidationStatus

    def __post_init__(self) -> None:
        if (type(self.code) is not str or not self.code
                or not _status(self.status)):
            raise StructuredSpecValidationContractError("invalid type check")


@dataclass(frozen=True, slots=True)
class StructuredSpecTypeChecks:
    spec_type: str
    checks: tuple[StructuredSpecTypeCheck, ...]

    def __post_init__(self) -> None:
        expected = _TYPE_CHECKS.get(self.spec_type)
        if (expected is None or type(self.checks) is not tuple
                or tuple(item.code for item in self.checks
                         if type(item) is StructuredSpecTypeCheck) != expected
                or len(self.checks) != len(expected)):
            raise StructuredSpecValidationContractError("invalid type checks")


def build_structured_spec_type_checks(
    spec_type: str, statuses: Mapping[str, ValidationStatus] | None = None,
) -> StructuredSpecTypeChecks:
    expected = _TYPE_CHECKS.get(spec_type)
    if expected is None or statuses is not None and (
            not isinstance(statuses, Mapping) or set(statuses) != set(expected)):
        raise StructuredSpecValidationContractError("invalid type check set")
    values = statuses or {code: "UNAVAILABLE" for code in expected}
    return StructuredSpecTypeChecks(spec_type, tuple(
        StructuredSpecTypeCheck(code, values[code]) for code in expected))


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationObservation:
    facts: StructuredSpecValidationFacts
    type_checks: StructuredSpecTypeChecks

    def __post_init__(self) -> None:
        if (type(self.facts) is not StructuredSpecValidationFacts
                or type(self.type_checks) is not StructuredSpecTypeChecks):
            raise StructuredSpecValidationContractError("invalid validation observation")


def audit_reason_for_observation(
    observation: StructuredSpecValidationObservation,
) -> str:
    if type(observation) is not StructuredSpecValidationObservation:
        raise StructuredSpecValidationContractError("invalid validation observation")
    letters = "".join(
        _STATUS_TO_LETTER[getattr(observation.facts, name)]
        for name in _DIMENSIONS)
    letters += "".join(_STATUS_TO_LETTER[item.status]
                       for item in observation.type_checks.checks)
    return (_AUDIT_REASON_PREFIX
            + _TYPE_CODES[observation.type_checks.spec_type] + "_" + letters)


def observation_from_audit_reason(
    reason: str,
) -> StructuredSpecValidationObservation:
    if type(reason) is not str or not reason.startswith(_AUDIT_REASON_PREFIX):
        raise StructuredSpecValidationContractError("invalid validation audit reason")
    suffix = reason[len(_AUDIT_REASON_PREFIX):]
    if len(suffix) < 4 or suffix[2] != "_" or suffix[:2] not in _CODE_TYPES:
        raise StructuredSpecValidationContractError("invalid validation audit reason")
    spec_type = _CODE_TYPES[suffix[:2]]
    letters = suffix[3:]
    expected = len(_DIMENSIONS) + len(_TYPE_CHECKS[spec_type])
    if len(letters) != expected:
        raise StructuredSpecValidationContractError("invalid validation audit reason")
    try:
        statuses = tuple(_LETTER_TO_STATUS[letter] for letter in letters)
        facts = StructuredSpecValidationFacts(**dict(zip(
            _DIMENSIONS, statuses[:len(_DIMENSIONS)], strict=True)))
        checks = build_structured_spec_type_checks(spec_type, dict(zip(
            _TYPE_CHECKS[spec_type], statuses[len(_DIMENSIONS):], strict=True)))
        return StructuredSpecValidationObservation(facts, checks)
    except (KeyError, TypeError, ValueError):
        raise StructuredSpecValidationContractError(
            "invalid validation audit reason") from None


def _issues(snapshot: StructuredSpecValidationSnapshot,
            observation: StructuredSpecValidationObservation) -> tuple[str, ...]:
    issues: list[str] = []
    if snapshot.version_state != "DRAFT":
        issues.append("VERSION_NOT_DRAFT")
    issues.extend(f"{_ISSUE_NAMES[name]}_{getattr(observation.facts, name)}"
                  for name in _DIMENSIONS
                  if getattr(observation.facts, name) != "PASS")
    issues.extend(f"{item.code}_{item.status}"
                  for item in observation.type_checks.checks
                  if item.status != "PASS")
    return tuple(issues)


def _conclusions(snapshot: StructuredSpecValidationSnapshot,
                 observation: StructuredSpecValidationObservation) -> tuple[bool, bool]:
    valid = all(getattr(observation.facts, name) == "PASS"
                for name in _VALID_DIMENSIONS)
    ready = (valid and snapshot.version_state == "DRAFT"
             and all(getattr(observation.facts, name) == "PASS"
                     for name in ("artifacts", "trace", "current_version"))
             and all(item.status == "PASS"
                     for item in observation.type_checks.checks))
    return valid, ready


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    project_id: uuid.UUID
    structured_solution_spec_id: uuid.UUID
    spec_series_id: uuid.UUID
    spec_type: str
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    requirement_count: int
    section_count: int
    evidence_count: int
    artifact_count: int
    facts: StructuredSpecValidationFacts
    type_checks: StructuredSpecTypeChecks
    valid: bool
    ready_for_review: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        try:
            snapshot = StructuredSpecValidationSnapshot(
                self.project_id, self.structured_solution_spec_id,
                self.spec_series_id, self.spec_type, self.version_no,
                self.version_state, self.content_fingerprint,
                self.payload_fingerprint, self.requirement_count,
                self.section_count, self.evidence_count, self.artifact_count)
            observation = StructuredSpecValidationObservation(
                self.facts, self.type_checks)
        except StructuredSpecValidationContractError:
            raise StructuredSpecValidationContractError(
                "invalid validation report") from None
        valid, ready = _conclusions(snapshot, observation)
        if (not _id(self.audit_event_id) or not _id(self.trace_id)
                or self.type_checks.spec_type != self.spec_type
                or type(self.valid) is not bool
                or type(self.ready_for_review) is not bool
                or type(self.issue_codes) is not tuple
                or self.issue_codes != _issues(snapshot, observation)
                or self.valid != valid or self.ready_for_review != ready
                or not _aware(self.observed_at)):
            raise StructuredSpecValidationContractError("invalid validation report")


def build_structured_spec_validation_report(
    command: ValidateStructuredSpec,
    snapshot: StructuredSpecValidationSnapshot,
    observation: StructuredSpecValidationObservation,
    *, audit_event_id: uuid.UUID,
    observed_at: datetime,
) -> StructuredSpecValidationReport:
    if (type(command) is not ValidateStructuredSpec
            or type(snapshot) is not StructuredSpecValidationSnapshot
            or type(observation) is not StructuredSpecValidationObservation
            or (command.project_id, command.structured_solution_spec_id) != (
                snapshot.project_id, snapshot.structured_solution_spec_id)
            or observation.type_checks.spec_type != snapshot.spec_type):
        raise StructuredSpecValidationContractError("validation identity mismatch")
    valid, ready = _conclusions(snapshot, observation)
    return StructuredSpecValidationReport(
        audit_event_id=audit_event_id, trace_id=command.trace_id,
        project_id=snapshot.project_id,
        structured_solution_spec_id=snapshot.structured_solution_spec_id,
        spec_series_id=snapshot.spec_series_id, spec_type=snapshot.spec_type,
        version_no=snapshot.version_no, version_state=snapshot.version_state,
        content_fingerprint=snapshot.content_fingerprint,
        payload_fingerprint=snapshot.payload_fingerprint,
        requirement_count=snapshot.requirement_count,
        section_count=snapshot.section_count,
        evidence_count=snapshot.evidence_count,
        artifact_count=snapshot.artifact_count,
        facts=observation.facts, type_checks=observation.type_checks,
        valid=valid, ready_for_review=ready,
        issue_codes=_issues(snapshot, observation), observed_at=observed_at)
