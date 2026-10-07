"""Idempotent current-fact validation for an immutable SurveyConclusion."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.survey_conclusion_task import (
    SurveyConclusionAITaskProof,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.handover.application.survey_conclusion_issue import (
    SurveyConclusionIssueProof,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)

from .conclusion_sources import (
    ConclusionProjectRecordProof, ConclusionProjectRecordQuery,
    ConclusionResponseProof, SurveyConclusionSourceError,
)
from .create_conclusion import (
    ConclusionEvidenceInput, ConclusionOpenIssueInput, CreateSurveyConclusion,
    DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateService,
)


_ORDER = (
    "CONTENT_FINGERPRINT_MISMATCH", "COUNT_MISMATCH",
    "ROUND_UNAVAILABLE", "RESPONSE_UNAVAILABLE", "EVIDENCE_UNAVAILABLE",
    "AI_PROVENANCE_UNAVAILABLE", "OPEN_ISSUE_UNAVAILABLE",
    "CONFLICT_EVIDENCE_PRESENT", "BLOCKING_OPEN_ISSUE",
    "SOURCE_COVERAGE_MISSING", "FORMAL_DECISION_UNVERIFIED",
)
_LETTERS = dict(zip(_ORDER, "FCRVEAIOBSU", strict=True))
_BY_LETTER = {value: key for key, value in _LETTERS.items()}
_OPERATION = "V1_SURVEY_CONCLUSION_VALIDATE"


class SurveyConclusionValidationError(RuntimeError):
    def __init__(self, code: str = "SURVEY_CONCLUSION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidateSurveyConclusion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_conclusion_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ConclusionValidationSnapshot:
    survey_conclusion_id: uuid.UUID
    conclusion_series_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    round_refs: tuple[uuid.UUID, ...]
    ai_task_refs: tuple[uuid.UUID, ...]
    version_no: int
    conclusion_state: str
    content_fingerprint: bytes = field(repr=False)
    declared_department_count: int
    declared_module_count: int
    declared_evidence_count: int
    declared_open_issue_count: int
    supersedes_ref: uuid.UUID | None
    departments: tuple[DepartmentConclusionInput, ...]
    modules: tuple[ModuleConclusionInput, ...]
    evidence: tuple[ConclusionProjectRecordProof, ...]
    evidence_roles: tuple[str, ...]
    issues: tuple[SurveyConclusionIssueProof, ...]
    issue_blocking: tuple[bool, ...]
    rounds_current: bool
    ordinals_contiguous: bool
    formal_decision_count: int


@dataclass(frozen=True, slots=True)
class ConclusionValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str


@dataclass(frozen=True, slots=True)
class SurveyConclusionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    survey_conclusion_id: uuid.UUID
    conclusion_series_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    version_no: int
    conclusion_state: str
    department_count: int
    module_count: int
    evidence_count: int
    open_issue_count: int
    response_count: int
    support_evidence_count: int
    conflict_evidence_count: int
    current_open_blocking_issue_count: int
    valid: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime


class ConclusionValidationRepositoryPort(Protocol):
    def lock_snapshot(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID,
    ) -> ConclusionValidationSnapshot | None: ...


class ConclusionValidationAuditPort(Protocol):
    def get(
        self, transaction: object, *, audit_event_id: uuid.UUID,
        actor_id: uuid.UUID, project_id: uuid.UUID,
        conclusion_series_id: uuid.UUID, survey_conclusion_id: uuid.UUID,
    ) -> ConclusionValidationAudit | None: ...


@dataclass(frozen=True, slots=True)
class _CurrentFacts:
    issues: tuple[str, ...]
    response_count: int
    support_evidence_count: int
    conflict_evidence_count: int
    current_open_blocking_issue_count: int


class SurveyConclusionCurrentValidator:
    """Re-prove every mutable source in the caller transaction."""

    def __init__(self, *, response_owner: object, evidence_owner: object,
                 issue_owner: object, ai_owner: object) -> None:
        if any(value is None for value in (
                response_owner, evidence_owner, issue_owner, ai_owner)):
            raise ValueError("Survey Conclusion source owners required")
        self._responses, self._evidence = response_owner, evidence_owner
        self._issues, self._ai = issue_owner, ai_owner

    def current_facts(
        self, tx: object, command: ValidateSurveyConclusion,
        snapshot: ConclusionValidationSnapshot,
    ) -> _CurrentFacts:
        if (type(command) is not ValidateSurveyConclusion
                or type(snapshot) is not ConclusionValidationSnapshot):
            raise SurveyConclusionValidationError()
        found: set[str] = set()
        if not snapshot.rounds_current:
            found.add("ROUND_UNAVAILABLE")
        response_ids = tuple(sorted({
            response_id
            for item in (*snapshot.departments, *snapshot.modules)
            for response_id in item.response_refs
        }, key=lambda value: value.int))
        response_proofs: list[ConclusionResponseProof] = []
        expected_departments = {
            response_id: item.department_id
            for item in snapshot.departments
            for response_id in item.response_refs
        }
        for response_id in response_ids:
            proof = self._responses.prove(
                tx, project_id=snapshot.project_id, survey_id=snapshot.survey_id,
                round_refs=snapshot.round_refs, response_id=response_id,
            )
            if not self._valid_response(
                    proof, snapshot, response_id,
                    expected_departments.get(response_id)):
                found.add("RESPONSE_UNAVAILABLE")
            else:
                response_proofs.append(proof)

        for stored in snapshot.evidence:
            try:
                proof = self._evidence.prove(
                    tx, ConclusionProjectRecordQuery(
                        command.session_token, command.trace_id,
                        snapshot.project_id, stored.evidence_id,
                    ),
                )
            except SurveyConclusionSourceError:
                proof = None
            if not self._same_evidence(proof, stored):
                found.add("EVIDENCE_UNAVAILABLE")

        open_blocking = 0
        for stored, is_blocking in zip(
                snapshot.issues, snapshot.issue_blocking, strict=False):
            proof = self._issues.prove(
                tx, project_id=snapshot.project_id,
                action_item_id=stored.action_item_id,
            )
            if not self._valid_issue(proof, snapshot, stored.action_item_id):
                found.add("OPEN_ISSUE_UNAVAILABLE")
                if is_blocking:
                    open_blocking += 1
            else:
                if is_blocking and proof.action_state not in {"CLOSED", "CANCELLED"}:
                    open_blocking += 1
        if open_blocking:
            found.add("BLOCKING_OPEN_ISSUE")

        ai_proofs: list[SurveyConclusionAITaskProof] = []
        for ai_task_id in snapshot.ai_task_refs:
            proof = self._ai.prove(
                tx, project_id=snapshot.project_id, ai_task_id=ai_task_id,
            )
            if not self._valid_ai(proof, snapshot, ai_task_id):
                found.add("AI_PROVENANCE_UNAVAILABLE")
            else:
                ai_proofs.append(proof)

        conflict_count = sum(
            role == "CONFLICT" for role in snapshot.evidence_roles)
        support_count = sum(role == "SUPPORT" for role in snapshot.evidence_roles)
        if conflict_count:
            found.add("CONFLICT_EVIDENCE_PRESENT")
        if not response_ids and not support_count:
            found.add("SOURCE_COVERAGE_MISSING")
        if snapshot.formal_decision_count:
            found.add("FORMAL_DECISION_UNVERIFIED")
        if self._count_mismatch(snapshot):
            found.add("COUNT_MISMATCH")
        if (len(response_proofs) == len(response_ids)
                and len(ai_proofs) == len(snapshot.ai_task_refs)
                and not self._fingerprint_matches(
                    snapshot, response_proofs, ai_proofs)):
            found.add("CONTENT_FINGERPRINT_MISMATCH")
        return _CurrentFacts(
            tuple(code for code in _ORDER if code in found), len(response_ids),
            support_count, conflict_count, open_blocking,
        )

    @staticmethod
    def _valid_response(proof: object, snapshot: ConclusionValidationSnapshot,
                        response_id: uuid.UUID,
                        expected_department: uuid.UUID | None) -> bool:
        return (type(proof) is ConclusionResponseProof
                and proof.response_id == response_id
                and proof.project_id == snapshot.project_id
                and proof.survey_id == snapshot.survey_id
                and proof.round_id in snapshot.round_refs
                and type(proof.answer_fingerprint) is bytes
                and len(proof.answer_fingerprint) == 32
                and (expected_department is None
                     or proof.department_id == expected_department))

    @staticmethod
    def _same_evidence(proof: object,
                       stored: ConclusionProjectRecordProof) -> bool:
        return (type(proof) is ConclusionProjectRecordProof
                and proof.evidence_id == stored.evidence_id
                and proof.project_id == stored.project_id
                and proof.document_id == stored.document_id
                and proof.document_version_id == stored.document_version_id
                and proof.observed_evidence_lock_version
                == stored.observed_evidence_lock_version
                and type(proof.content_fingerprint) is bytes
                and hmac.compare_digest(
                    proof.content_fingerprint, stored.content_fingerprint))

    @staticmethod
    def _valid_issue(proof: object, snapshot: ConclusionValidationSnapshot,
                     issue_id: uuid.UUID) -> bool:
        return (type(proof) is SurveyConclusionIssueProof
                and proof.action_item_id == issue_id
                and proof.project_id == snapshot.project_id
                and proof.action_state in {
                    "OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED",
                    "CLOSED", "CANCELLED",
                }
                and type(proof.lock_version) is int and proof.lock_version >= 0)

    @staticmethod
    def _valid_ai(proof: object, snapshot: ConclusionValidationSnapshot,
                  ai_task_id: uuid.UUID) -> bool:
        return (type(proof) is SurveyConclusionAITaskProof
                and proof.ai_task_id == ai_task_id
                and proof.project_id == snapshot.project_id
                and proof.fact_status == "NOT_FORMAL_FACT"
                and proof.suggestion_state in {"AVAILABLE", "ACCEPTED_TO_DRAFT"}
                and type(proof.payload_fingerprint) is bytes
                and len(proof.payload_fingerprint) == 32)

    @staticmethod
    def _count_mismatch(snapshot: ConclusionValidationSnapshot) -> bool:
        return (not snapshot.ordinals_contiguous
                or snapshot.declared_department_count != len(snapshot.departments)
                or snapshot.declared_module_count != len(snapshot.modules)
                or snapshot.declared_evidence_count != len(snapshot.evidence)
                or snapshot.declared_open_issue_count != len(snapshot.issues)
                or len(snapshot.evidence) != len(snapshot.evidence_roles)
                or len(snapshot.issues) != len(snapshot.issue_blocking))

    @staticmethod
    def _fingerprint_matches(
        snapshot: ConclusionValidationSnapshot,
        response_proofs: list[ConclusionResponseProof],
        ai_proofs: list[SurveyConclusionAITaskProof],
    ) -> bool:
        command = CreateSurveyConclusion(
            b"x" * 32, b"x" * 32, snapshot.survey_conclusion_id,
            snapshot.project_id, snapshot.survey_id, snapshot.round_refs,
            snapshot.departments, snapshot.modules,
            tuple(ConclusionEvidenceInput(item.evidence_id, role)
                  for item, role in zip(
                      snapshot.evidence, snapshot.evidence_roles, strict=False)),
            tuple(ConclusionOpenIssueInput(item.action_item_id, is_blocking)
                  for item, is_blocking in zip(
                      snapshot.issues, snapshot.issue_blocking, strict=False)),
            snapshot.ai_task_refs, snapshot.supersedes_ref, "x" * 16,
        )
        fingerprint = canonical_payload_fingerprint(
            SurveyConclusionCreateService._snapshot_payload(
                command, tuple(response_proofs),
                tuple(sorted(snapshot.evidence,
                             key=lambda item: item.evidence_id.int)),
                tuple(sorted(snapshot.issues,
                             key=lambda item: item.action_item_id.int)),
                tuple(ai_proofs),
            ),
        )
        return (type(snapshot.content_fingerprint) is bytes
                and len(snapshot.content_fingerprint) == 32
                and hmac.compare_digest(fingerprint, snapshot.content_fingerprint))


class SurveyConclusionValidationService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: ConclusionValidationRepositoryPort,
        response_owner: object, evidence_owner: object, issue_owner: object,
        ai_owner: object, audit_source: ConclusionValidationAuditPort,
        receipts: object, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        dependencies = (
            unit_of_work, access, license_guard, authorization, repository,
            response_owner, evidence_owner, issue_owner, ai_owner, audit_source,
            receipts, audit,
        )
        if any(value is None for value in dependencies):
            raise ValueError("Survey Conclusion validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._current = SurveyConclusionCurrentValidator(
            response_owner=response_owner, evidence_owner=evidence_owner,
            issue_owner=issue_owner, ai_owner=ai_owner,
        )
        self._audit_source, self._receipts, self._audit = (
            audit_source, receipts, audit)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(
        self, command: ValidateSurveyConclusion,
    ) -> SurveyConclusionValidationReport:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            request = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_conclusion_id": str(command.survey_conclusion_id),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_CONCLUSION_VALIDATE",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_CONCLUSION_VALIDATE"
                        or authorized.project_role not in {
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}):
                    raise SurveyConclusionValidationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request)
                snapshot = self._repository.lock_snapshot(
                    tx, project_id=command.project_id,
                    survey_conclusion_id=command.survey_conclusion_id,
                )
                if type(snapshot) is not ConclusionValidationSnapshot:
                    raise SurveyConclusionValidationError("RESOURCE_NOT_FOUND")
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise SurveyConclusionValidationError()
                    proof = self._audit_source.get(
                        tx, audit_event_id=replay.ref_id, actor_id=actor,
                        project_id=command.project_id,
                        conclusion_series_id=snapshot.conclusion_series_id,
                        survey_conclusion_id=command.survey_conclusion_id,
                    )
                    if type(proof) is not ConclusionValidationAudit:
                        raise SurveyConclusionValidationError()
                    return self._report(snapshot, proof)
                facts = self._current.current_facts(tx, command, snapshot)
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None,
                    action="SURVEY_CONCLUSION_VALIDATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-05",
                    target_object_id=snapshot.conclusion_series_id,
                    target_version_id=snapshot.survey_conclusion_id,
                    reason_code=self._reason(facts),
                    before_state=snapshot.conclusion_state,
                    after_state=snapshot.conclusion_state,
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyConclusionValidationError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, audit_id, 200,
                ))
                proof = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    conclusion_series_id=snapshot.conclusion_series_id,
                    survey_conclusion_id=command.survey_conclusion_id,
                )
                if type(proof) is not ConclusionValidationAudit:
                    raise SurveyConclusionValidationError()
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return self._report(snapshot, proof)
        except SurveyConclusionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyConclusionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyConclusionValidationError(
                "LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyConclusionValidationError(error.code) from None
        except Exception:
            raise SurveyConclusionValidationError() from None

    @staticmethod
    def _validate(command: ValidateSurveyConclusion) -> None:
        if (type(command) is not ValidateSurveyConclusion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id,
                    command.survey_conclusion_id))):
            raise SurveyConclusionValidationError("VALIDATION_FAILED")

    def _actor(self, tx: object,
               command: ValidateSurveyConclusion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyConclusionValidationError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyConclusionValidationError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _reason(facts: _CurrentFacts) -> str:
        letters = "".join(_LETTERS[issue] for issue in facts.issues)
        # Counts are persisted so idempotent replay returns the original facts.
        return ("CONCLUSION_VALIDATION_PASSED_"
                if not facts.issues else "CONCLUSION_VALIDATION_FAILED_") + (
            f"{letters}_{facts.response_count}_{facts.support_evidence_count}_"
            f"{facts.conflict_evidence_count}_"
            f"{facts.current_open_blocking_issue_count}"
        )

    @staticmethod
    def _decode(reason: str) -> tuple[tuple[str, ...], tuple[int, int, int, int]]:
        passed = "CONCLUSION_VALIDATION_PASSED_"
        failed = "CONCLUSION_VALIDATION_FAILED_"
        if reason.startswith(passed):
            valid, body = True, reason[len(passed):]
        elif reason.startswith(failed):
            valid, body = False, reason[len(failed):]
        else:
            raise SurveyConclusionValidationError()
        parts = body.split("_")
        if len(parts) != 5:
            raise SurveyConclusionValidationError()
        letters = parts[0]
        try:
            issues = tuple(_BY_LETTER[value] for value in letters)
            counts = tuple(int(value) for value in parts[1:])
        except (KeyError, ValueError):
            raise SurveyConclusionValidationError() from None
        if (any(value < 0 for value in counts)
                or tuple(code for code in _ORDER if code in issues) != issues
                or valid != (not issues)):
            raise SurveyConclusionValidationError()
        return issues, counts  # type: ignore[return-value]

    @staticmethod
    def _report(
        snapshot: ConclusionValidationSnapshot,
        proof: ConclusionValidationAudit,
    ) -> SurveyConclusionValidationReport:
        issues, counts = SurveyConclusionValidationService._decode(
            proof.reason_code)
        return SurveyConclusionValidationReport(
            proof.audit_event_id, proof.trace_id,
            snapshot.survey_conclusion_id, snapshot.conclusion_series_id,
            snapshot.project_id, snapshot.survey_id, snapshot.version_no,
            snapshot.conclusion_state, len(snapshot.departments),
            len(snapshot.modules), len(snapshot.evidence), len(snapshot.issues),
            *counts, not issues, issues, proof.observed_at,
        )
