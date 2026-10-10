"""Idempotent current-fact validation for an immutable RequirementVersion."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.capability.application.requirement_source_proof import (
    CapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.handover.application.requirement_source_proof import (
    HandoverRequirementSourceProof,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.survey.application.requirement_source_proof import (
    SurveyConclusionRequirementSourceProof,
)

from .create_version import (
    RequirementAcceptanceDraft, RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
)
from .human_decision_source_proof import RequirementHumanDecisionSourceProof


_ORDER = (
    "CONTENT_FINGERPRINT_MISMATCH", "COUNT_MISMATCH", "STRUCTURE_INVALID",
    "SOURCE_UNAVAILABLE", "CAPABILITY_UNAVAILABLE", "EVIDENCE_UNAVAILABLE",
    "ACCEPTANCE_CRITERIA_MISSING", "ACCEPTANCE_CRITERIA_CONFLICT",
    "DECLARATION_CONFLICT", "CLASSIFICATION_INCONSISTENT",
    "PENDING_CONFIRMATION",
)
_LETTERS = dict(zip(_ORDER, "FQUSCEMADNP", strict=True))
_BY_LETTER = {letter: issue for issue, letter in _LETTERS.items()}
_OPERATION = "V1_REQ_VERSION_VALIDATE"


class RequirementVersionValidationError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidateRequirementVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementVersionValidationSnapshot:
    requirement_version_id: uuid.UUID
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    title: str | None
    statement: str
    rationale: str
    domain_name: str
    priority: str
    risk: str
    classification: str
    content_fingerprint: bytes = field(repr=False)
    declared_source_count: int
    declared_acceptance_count: int
    declared_capability_count: int
    declared_assumption_count: int
    declared_exclusion_count: int
    declared_dependency_count: int
    declared_ai_task_count: int
    sources: tuple[RequirementSourceDraft, ...]
    acceptance_criteria: tuple[RequirementAcceptanceDraft, ...]
    capability_assessments: tuple[RequirementCapabilityAssessmentDraft, ...]
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    dependencies: tuple[str, ...]
    ai_task_refs: tuple[uuid.UUID, ...]
    ordinals_contiguous: bool


@dataclass(frozen=True, slots=True)
class RequirementValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str


@dataclass(frozen=True, slots=True)
class RequirementVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    classification: str
    source_count: int
    acceptance_count: int
    capability_count: int
    assumption_count: int
    exclusion_count: int
    dependency_count: int
    evidence_ref_count: int
    valid: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime


class RequirementVersionValidationRepositoryPort(Protocol):
    def lock_snapshot(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> RequirementVersionValidationSnapshot | None: ...


class RequirementValidationAuditPort(Protocol):
    def get(
        self, transaction: object, *, audit_event_id: uuid.UUID,
        actor_id: uuid.UUID, project_id: uuid.UUID,
        requirement_version_id: uuid.UUID,
    ) -> RequirementValidationAudit | None: ...


class RequirementVersionCurrentValidator:
    """Revalidate immutable content and all external facts in the caller's tx."""

    def __init__(self, *, survey_sources: object, handover_sources: object,
                 human_decisions: object, project_evidence: object,
                 capability_sources: object, fixed_evidence: object) -> None:
        values = (survey_sources, handover_sources, human_decisions,
                  project_evidence, capability_sources, fixed_evidence)
        if any(value is None for value in values):
            raise ValueError("Requirement validation proof dependencies required")
        self._survey, self._handover = survey_sources, handover_sources
        self._decisions, self._project_evidence = human_decisions, project_evidence
        self._capability, self._fixed_evidence = capability_sources, fixed_evidence

    def current_issues(
        self, tx: object, snapshot: RequirementVersionValidationSnapshot,
    ) -> tuple[str, ...]:
        return self.current_issues_and_project_evidence(tx, snapshot)[0]

    def current_issues_and_project_evidence(
        self, tx: object, snapshot: RequirementVersionValidationSnapshot,
    ) -> tuple[tuple[str, ...], tuple[EvidenceRequirementSourceProof, ...]]:
        """Return only proofs checked within this same locked validation call."""
        if type(snapshot) is not RequirementVersionValidationSnapshot:
            raise RequirementVersionValidationError()
        found: set[str] = set()
        project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None] = {}
        payload = self._content_payload(snapshot, found)
        if payload is not None and not hmac.compare_digest(
                canonical_payload_fingerprint(payload), snapshot.content_fingerprint):
            found.add("CONTENT_FINGERPRINT_MISMATCH")
        self._counts(snapshot, found)
        self._business_rules(snapshot, found)
        self._source_issues(tx, snapshot, found, project_evidence)
        self._capability_issues(tx, snapshot, found, project_evidence)
        issues = tuple(issue for issue in _ORDER if issue in found)
        if issues:
            return issues, ()
        return issues, tuple(
            project_evidence[evidence_id]
            for evidence_id in sorted(project_evidence, key=lambda value: value.int)
            if type(project_evidence[evidence_id]) is EvidenceRequirementSourceProof
        )

    @staticmethod
    def _content_payload(
        snapshot: RequirementVersionValidationSnapshot, found: set[str],
    ) -> dict[str, object] | None:
        try:
            sources = [RequirementVersionCurrentValidator._jsonable(item)
                       for item in snapshot.sources]
            criteria = [RequirementVersionCurrentValidator._jsonable(item)
                        for item in snapshot.acceptance_criteria]
            assessments = [RequirementVersionCurrentValidator._jsonable(item)
                           for item in snapshot.capability_assessments]
            if (any(type(value) is not str or not value or value != value.strip()
                    for value in (snapshot.statement, snapshot.rationale,
                                  snapshot.domain_name))
                    or type(snapshot.content_fingerprint) is not bytes
                    or len(snapshot.content_fingerprint) != 32):
                raise ValueError("invalid snapshot")
            return {
                "project_id": str(snapshot.project_id),
                "requirement_id": str(snapshot.requirement_id),
                "title": snapshot.title,
                "statement": snapshot.statement,
                "rationale": snapshot.rationale,
                "domain_name": snapshot.domain_name,
                "priority": snapshot.priority,
                "risk": snapshot.risk,
                "classification": snapshot.classification,
                "sources": sources,
                "acceptance_criteria": criteria,
                "capability_assessments": assessments,
                "assumptions": list(snapshot.assumptions),
                "exclusions": list(snapshot.exclusions),
                "dependencies": list(snapshot.dependencies),
                "ai_task_refs": [str(value) for value in snapshot.ai_task_refs],
            }
        except (AttributeError, TypeError, ValueError):
            found.add("STRUCTURE_INVALID")
            return None

    @staticmethod
    def _jsonable(value: object) -> dict[str, object]:
        def convert(item: object) -> object:
            if isinstance(item, uuid.UUID):
                return str(item)
            if isinstance(item, tuple):
                return [convert(nested) for nested in item]
            if isinstance(item, dict):
                return {key: convert(nested) for key, nested in item.items()}
            return item
        result = convert(asdict(value))
        if type(result) is not dict:
            raise ValueError("invalid aggregate item")
        return result

    @staticmethod
    def _counts(snapshot: RequirementVersionValidationSnapshot,
                found: set[str]) -> None:
        pairs = (
            (snapshot.sources, snapshot.declared_source_count),
            (snapshot.acceptance_criteria, snapshot.declared_acceptance_count),
            (snapshot.capability_assessments, snapshot.declared_capability_count),
            (snapshot.assumptions, snapshot.declared_assumption_count),
            (snapshot.exclusions, snapshot.declared_exclusion_count),
            (snapshot.dependencies, snapshot.declared_dependency_count),
            (snapshot.ai_task_refs, snapshot.declared_ai_task_count),
        )
        if (not snapshot.ordinals_contiguous
                or any(type(values) is not tuple or type(declared) is not int
                       or declared != len(values) for values, declared in pairs)):
            found.add("COUNT_MISMATCH")

    @staticmethod
    def _business_rules(snapshot: RequirementVersionValidationSnapshot,
                        found: set[str]) -> None:
        if not snapshot.acceptance_criteria:
            found.add("ACCEPTANCE_CRITERIA_MISSING")
        criteria = {
            tuple(value.casefold() for value in (
                item.observable_result, item.verification_method,
                item.required_data, item.required_environment,
                item.evidence_requirement,
            )) for item in snapshot.acceptance_criteria
        }
        if len(criteria) != len(snapshot.acceptance_criteria):
            found.add("ACCEPTANCE_CRITERIA_CONFLICT")
        assumptions = {value.casefold() for value in snapshot.assumptions}
        exclusions = {value.casefold() for value in snapshot.exclusions}
        if assumptions & exclusions:
            found.add("DECLARATION_CONFLICT")
        confirmed = tuple(item for item in snapshot.capability_assessments
                          if item.confirmation_state == "CONFIRMED")
        if snapshot.classification == "STANDARD_FUNCTION":
            consistent = any(item.match_type == "DIRECT" for item in confirmed)
        elif snapshot.classification in {"NONSTANDARD_FUNCTION", "DIFFERENCE"}:
            consistent = (bool(snapshot.exclusions)
                          and any(item.match_type in {"PARTIAL", "NONE"}
                                  for item in confirmed))
        elif snapshot.classification == "PENDING_CONFIRMATION":
            consistent = True
            found.add("PENDING_CONFIRMATION")
        else:
            consistent = False
        if not consistent:
            found.add("CLASSIFICATION_INCONSISTENT")

    def _source_issues(self, tx: object,
                       snapshot: RequirementVersionValidationSnapshot,
                       found: set[str],
                       project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None]) -> None:
        for source in snapshot.sources:
            if not self._source_current(tx, snapshot, source, project_evidence):
                found.add("SOURCE_UNAVAILABLE")
            for evidence_id in source.evidence_refs:
                if not self._project_evidence_current(
                        tx, snapshot.project_id, evidence_id,
                        project_evidence):
                    found.add("EVIDENCE_UNAVAILABLE")

    def _source_current(self, tx: object,
                        snapshot: RequirementVersionValidationSnapshot,
                        source: RequirementSourceDraft,
                        project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None]) -> bool:
        if source.source_type == "APPROVED_SURVEY_CONCLUSION":
            proof = self._survey.prove(
                tx, project_id=snapshot.project_id,
                survey_conclusion_id=source.source_object_id,
            )
            return (type(proof) is SurveyConclusionRequirementSourceProof
                    and proof.survey_conclusion_id == source.source_object_id
                    and proof.project_id == snapshot.project_id)
        if source.source_type == "CONFIRMED_HANDOVER":
            proof = self._handover.prove(
                tx, project_id=snapshot.project_id,
                handover_analysis_id=source.source_object_id,
                handover_analysis_version_id=source.source_version_ref,
            )
            return (type(proof) is HandoverRequirementSourceProof
                    and proof.handover_analysis_id == source.source_object_id
                    and proof.handover_analysis_version_id == source.source_version_ref
                    and proof.project_id == snapshot.project_id)
        if source.source_type == "HUMAN_DECISION":
            proof = self._decisions.prove(
                tx, project_id=snapshot.project_id,
                decision_id=source.source_object_id,
            )
            return (type(proof) is RequirementHumanDecisionSourceProof
                    and proof.decision_id == source.source_object_id
                    and proof.requirement_id == snapshot.requirement_id
                    and proof.project_id == snapshot.project_id
                    and proof.evidence_refs == tuple(sorted(source.evidence_refs)))
        if source.source_type == "PROJECT_EVIDENCE":
            proof = self._project_evidence_proof(
                tx, snapshot.project_id, source.source_object_id,
                project_evidence,
            )
            return (type(proof) is EvidenceRequirementSourceProof
                    and proof.evidence_id == source.source_object_id
                    and proof.project_id == snapshot.project_id
                    and source.evidence_refs == (source.source_object_id,))
        return False

    def _capability_issues(self, tx: object,
                           snapshot: RequirementVersionValidationSnapshot,
                           found: set[str],
                           project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None]) -> None:
        for assessment in snapshot.capability_assessments:
            proof = self._capability.prove(
                tx, baseline_version_id=assessment.baseline_version_id,
                capability_item_id=assessment.capability_item_id,
            )
            if (type(proof) is not CapabilityRequirementSourceProof
                    or proof.baseline_version_id != assessment.baseline_version_id
                    or proof.capability_item_id != assessment.capability_item_id):
                found.add("CAPABILITY_UNAVAILABLE")
            for ref in assessment.evidence_refs:
                if ref.evidence_role == "PROJECT":
                    current = self._project_evidence_current(
                        tx, snapshot.project_id, ref.evidence_id,
                        project_evidence)
                elif ref.evidence_role == "STANDARD":
                    evidence = self._fixed_evidence.get_for_trace(
                        tx, scope="GLOBAL", project_id=None,
                        evidence_id=ref.evidence_id,
                    )
                    current = (type(evidence) is LockedEvidenceSource
                               and evidence.scope == "GLOBAL"
                               and evidence.project_id is None)
                else:
                    current = False
                if not current:
                    found.add("EVIDENCE_UNAVAILABLE")

    def _project_evidence_current(self, tx: object, project_id: uuid.UUID,
                                  evidence_id: uuid.UUID,
                                  project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None]) -> bool:
        proof = self._project_evidence_proof(
            tx, project_id, evidence_id, project_evidence,
        )
        return (type(proof) is EvidenceRequirementSourceProof
                and proof.evidence_id == evidence_id
                and proof.project_id == project_id)

    def _project_evidence_proof(self, tx: object, project_id: uuid.UUID,
                                evidence_id: uuid.UUID,
                                project_evidence: dict[uuid.UUID, EvidenceRequirementSourceProof | None]
                                ) -> EvidenceRequirementSourceProof | None:
        if evidence_id not in project_evidence:
            project_evidence[evidence_id] = self._project_evidence.prove(
                tx, project_id=project_id, evidence_id=evidence_id,
            )
        return project_evidence[evidence_id]


class RequirementVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 survey_sources: object, handover_sources: object,
                 human_decisions: object, project_evidence: object,
                 capability_sources: object, fixed_evidence: object,
                 repository: RequirementVersionValidationRepositoryPort,
                 audit_source: RequirementValidationAuditPort,
                 receipts: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, access, license_guard, authorization,
                        survey_sources, handover_sources, human_decisions,
                        project_evidence, capability_sources, fixed_evidence,
                        repository, audit_source, receipts, audit)
        if any(value is None for value in dependencies):
            raise ValueError("Requirement validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._repository, self._audit_source = repository, audit_source
        self._receipts, self._audit = receipts, audit
        self._current = RequirementVersionCurrentValidator(
            survey_sources=survey_sources, handover_sources=handover_sources,
            human_decisions=human_decisions, project_evidence=project_evidence,
            capability_sources=capability_sources, fixed_evidence=fixed_evidence,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(
        self, command: ValidateRequirementVersion,
    ) -> RequirementVersionValidationReport:
        self._validate_command(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            request = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "requirement_id": str(command.requirement_id),
                "requirement_version_id": str(command.requirement_version_id),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="REQ_VERSION_VALIDATE",
                )
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "REQ_VERSION_VALIDATE"):
                    raise RequirementVersionValidationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request,
                )
                snapshot = self._repository.lock_snapshot(
                    tx, project_id=command.project_id,
                    requirement_id=command.requirement_id,
                    requirement_version_id=command.requirement_version_id,
                )
                if type(snapshot) is not RequirementVersionValidationSnapshot:
                    raise RequirementVersionValidationError("RESOURCE_NOT_FOUND")
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise RequirementVersionValidationError()
                    proof = self._proof(tx, command, actor, replay.ref_id)
                    return self._report(snapshot, proof)
                issues = self._current.current_issues(tx, snapshot)
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action="REQUIREMENT_VERSION_VALIDATED",
                    outcome="SUCCESS", target_owner_module="requirement",
                    target_object_type="REQ-03",
                    target_object_id=command.requirement_version_id,
                    target_version_id=command.requirement_version_id,
                    reason_code=self._reason(issues),
                    before_state=snapshot.version_state,
                    after_state=snapshot.version_state,
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise RequirementVersionValidationError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, audit_id, 200,
                ))
                proof = self._proof(tx, command, actor, audit_id)
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return self._report(snapshot, proof)
        except RequirementVersionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementVersionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise RequirementVersionValidationError(error.code) from None
        except Exception:
            raise RequirementVersionValidationError() from None

    def _proof(self, tx: object, command: ValidateRequirementVersion,
               actor: uuid.UUID, audit_id: uuid.UUID) -> RequirementValidationAudit:
        proof = self._audit_source.get(
            tx, audit_event_id=audit_id, actor_id=actor,
            project_id=command.project_id,
            requirement_version_id=command.requirement_version_id,
        )
        if type(proof) is not RequirementValidationAudit:
            raise RequirementVersionValidationError()
        return proof

    @staticmethod
    def _reason(issues: tuple[str, ...]) -> str:
        return ("REQ_VALIDATION_PASSED" if not issues else
                "REQ_VALIDATION_FAILED_" + "".join(_LETTERS[item] for item in issues))

    @staticmethod
    def _issues(reason: str) -> tuple[str, ...]:
        if reason == "REQ_VALIDATION_PASSED":
            return ()
        prefix = "REQ_VALIDATION_FAILED_"
        if not reason.startswith(prefix):
            raise RequirementVersionValidationError()
        try:
            issues = tuple(_BY_LETTER[value] for value in reason[len(prefix):])
        except KeyError:
            raise RequirementVersionValidationError() from None
        if tuple(item for item in _ORDER if item in issues) != issues:
            raise RequirementVersionValidationError()
        return issues

    @classmethod
    def _report(cls, snapshot: RequirementVersionValidationSnapshot,
                proof: RequirementValidationAudit) -> RequirementVersionValidationReport:
        issues = cls._issues(proof.reason_code)
        evidence_count = sum(len(source.evidence_refs) for source in snapshot.sources)
        evidence_count += sum(len(item.evidence_refs)
                              for item in snapshot.capability_assessments)
        return RequirementVersionValidationReport(
            proof.audit_event_id, proof.trace_id, snapshot.requirement_id,
            snapshot.requirement_version_id, snapshot.project_id,
            snapshot.version_no, snapshot.version_state, snapshot.classification,
            len(snapshot.sources), len(snapshot.acceptance_criteria),
            len(snapshot.capability_assessments), len(snapshot.assumptions),
            len(snapshot.exclusions), len(snapshot.dependencies), evidence_count,
            not issues, issues, proof.observed_at,
        )

    @staticmethod
    def _validate_command(command: ValidateRequirementVersion) -> None:
        if (type(command) is not ValidateRequirementVersion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.requirement_id,
                    command.requirement_version_id))):
            raise RequirementVersionValidationError("VALIDATION_FAILED")

    def _actor(self, tx: object,
               command: ValidateRequirementVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementVersionValidationError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise RequirementVersionValidationError("AUTH_ACCESS_DENIED")
        return actor
