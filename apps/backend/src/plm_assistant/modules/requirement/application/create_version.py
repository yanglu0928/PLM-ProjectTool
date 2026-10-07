"""Atomic creation of a complete immutable RequirementVersion draft."""

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
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.survey.application.requirement_source_proof import (
    SurveyConclusionRequirementSourceProof,
)

from .human_decision_source_proof import RequirementHumanDecisionSourceProof


_SOURCES = {"APPROVED_SURVEY_CONCLUSION", "CONFIRMED_HANDOVER",
            "HUMAN_DECISION", "PROJECT_EVIDENCE"}
_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}
_RISKS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_CLASSIFICATIONS = {"STANDARD_FUNCTION", "NONSTANDARD_FUNCTION",
                    "DIFFERENCE", "PENDING_CONFIRMATION"}
_MATCHES = {"DIRECT", "PARTIAL", "NONE", "UNKNOWN"}
_CONFIRMATIONS = {"CANDIDATE", "CONFIRMED", "REJECTED"}


class RequirementVersionCreateError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RequirementSourceDraft:
    source_type: str
    source_object_id: uuid.UUID
    source_version_ref: uuid.UUID | None = None
    evidence_refs: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementAcceptanceDraft:
    observable_result: str
    verification_method: str
    required_data: str
    required_environment: str
    evidence_requirement: str


@dataclass(frozen=True, slots=True)
class RequirementAssessmentEvidenceDraft:
    evidence_id: uuid.UUID
    evidence_role: str


@dataclass(frozen=True, slots=True)
class RequirementCapabilityAssessmentDraft:
    baseline_version_id: uuid.UUID
    capability_item_id: uuid.UUID
    match_type: str
    fit_gap: str
    constraints_text: str
    assessor_kind: str
    confirmation_state: str
    evidence_refs: tuple[RequirementAssessmentEvidenceDraft, ...]


@dataclass(frozen=True, slots=True)
class CreateRequirementVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    expected_lock_version: int
    initial: bool
    base_version_ref: uuid.UUID | None
    title: str | None
    statement: str
    rationale: str
    domain_name: str
    priority: str
    risk: str
    classification: str
    sources: tuple[RequirementSourceDraft, ...]
    acceptance_criteria: tuple[RequirementAcceptanceDraft, ...]
    capability_assessments: tuple[RequirementCapabilityAssessmentDraft, ...]
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    dependencies: tuple[str, ...]
    ai_task_refs: tuple[uuid.UUID, ...] = ()
    client_reason: str = "Create RequirementVersion draft"
    idempotency_key: str = field(default="", repr=False)


@dataclass(frozen=True, slots=True)
class RequirementVersionRootLock:
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    requirement_state: str
    lock_version: int
    highest_version_no: int
    latest_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class CreatedRequirementVersion:
    requirement_version_id: uuid.UUID
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(v) is not uuid.UUID or v.int == 0 for v in (
                self.requirement_version_id, self.requirement_id,
                self.project_id, self.created_by))
                or self.version_no < 1 or self.version_state != "DRAFT"
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or self.lock_version != self.expected_lock_version + 1
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None):
            raise RequirementVersionCreateError()


class RequirementVersionCreateRepositoryPort(Protocol):
    def lock_requirement(self, transaction: object, *, project_id: uuid.UUID,
                         requirement_id: uuid.UUID) -> RequirementVersionRootLock | None: ...
    def create(self, transaction: object, *, root: RequirementVersionRootLock,
               requirement_version_id: uuid.UUID, actor_id: uuid.UUID,
               content_fingerprint: bytes,
               command: CreateRequirementVersion) -> CreatedRequirementVersion: ...
    def initial_view(self, transaction: object, *, project_id: uuid.UUID,
                     requirement_id: uuid.UUID,
                     requirement_version_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedRequirementVersion | None: ...


class RequirementVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: RequirementVersionCreateRepositoryPort, receipts: object,
                 audit: AuditService, survey_sources: object, handover_sources: object,
                 human_decisions: object, project_evidence: object,
                 capability_sources: object, fixed_evidence: object,
                 clock: Callable[[], datetime] | None = None) -> None:
        values = (unit_of_work, access, license_guard, authorization, repository,
                  receipts, audit, survey_sources, handover_sources, human_decisions,
                  project_evidence, capability_sources, fixed_evidence)
        if any(value is None for value in values):
            raise ValueError("RequirementVersion create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._survey, self._handover = survey_sources, handover_sources
        self._decisions, self._project_evidence = human_decisions, project_evidence
        self._capability, self._fixed_evidence = capability_sources, fixed_evidence
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateRequirementVersion) -> CreatedRequirementVersion:
        payload = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            content = canonical_payload_fingerprint(payload)
            request = canonical_payload_fingerprint({
                "content_fingerprint": content.hex(),
                "expected_lock_version": command.expected_lock_version,
                "initial": command.initial,
                "base_version_ref": None if command.base_version_ref is None
                else str(command.base_version_ref),
                "client_reason": command.client_reason,
            })
            version_id = uuid.UUID(new_uuid7())
        except (IdempotencyError, ValueError):
            raise RequirementVersionCreateError("VALIDATION_FAILED") from None
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="REQ_VERSION_CREATE",
                )
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "REQ_VERSION_CREATE"):
                    raise RequirementVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation="V1_REQ_VERSION_CREATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request,
                )
                if replay is not None:
                    if (replay.ref_type != "V1_REQ_VERSION_CREATE"
                            or replay.status_code != 201):
                        raise RequirementVersionCreateError()
                    result = self._repository.initial_view(
                        tx, project_id=command.project_id,
                        requirement_id=command.requirement_id,
                        requirement_version_id=replay.ref_id,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if (type(result) is not CreatedRequirementVersion
                            or not hmac.compare_digest(result.content_fingerprint, content)):
                        raise RequirementVersionCreateError()
                    return result
                root = self._repository.lock_requirement(
                    tx, project_id=command.project_id,
                    requirement_id=command.requirement_id,
                )
                if type(root) is not RequirementVersionRootLock:
                    raise RequirementVersionCreateError("RESOURCE_NOT_FOUND")
                self._check_base(root, command)
                self._prove(tx, command)
                result = self._repository.create(
                    tx, root=root, requirement_version_id=version_id,
                    actor_id=actor, content_fingerprint=content, command=command,
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="REQUIREMENT_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="requirement", target_object_type="REQ-03",
                    target_object_id=version_id, target_version_id=version_id,
                    after_state="DRAFT",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise RequirementVersionCreateError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_REQ_VERSION_CREATE", version_id, 201,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except RequirementVersionCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise RequirementVersionCreateError(error.code) from None
        except Exception:
            raise RequirementVersionCreateError() from None

    @staticmethod
    def _check_base(root: RequirementVersionRootLock,
                    command: CreateRequirementVersion) -> None:
        if root.requirement_state != "ACTIVE":
            raise RequirementVersionCreateError("REQUIREMENT_STATE_CONFLICT")
        if root.lock_version != command.expected_lock_version:
            raise RequirementVersionCreateError("CONFLICT_VERSION")
        if command.initial:
            if root.latest_version_id is not None or root.highest_version_no != 0:
                raise RequirementVersionCreateError("CONFLICT_VERSION")
        elif (root.latest_version_id is None or root.highest_version_no < 1
              or command.base_version_ref != root.latest_version_id):
            raise RequirementVersionCreateError("CONFLICT_VERSION")

    def _prove(self, tx: object, command: CreateRequirementVersion) -> None:
        for source in command.sources:
            proof = None
            if source.source_type == "APPROVED_SURVEY_CONCLUSION":
                proof = self._survey.prove(tx, project_id=command.project_id,
                    survey_conclusion_id=source.source_object_id)
                valid = (type(proof) is SurveyConclusionRequirementSourceProof
                         and proof.survey_conclusion_id == source.source_object_id
                         and proof.project_id == command.project_id)
            elif source.source_type == "CONFIRMED_HANDOVER":
                proof = self._handover.prove(tx, project_id=command.project_id,
                    handover_analysis_id=source.source_object_id,
                    handover_analysis_version_id=source.source_version_ref)
                valid = (type(proof) is HandoverRequirementSourceProof
                         and proof.handover_analysis_id == source.source_object_id
                         and proof.handover_analysis_version_id == source.source_version_ref
                         and proof.project_id == command.project_id)
            elif source.source_type == "HUMAN_DECISION":
                proof = self._decisions.prove(tx, project_id=command.project_id,
                    decision_id=source.source_object_id)
                valid = (type(proof) is RequirementHumanDecisionSourceProof
                         and proof.decision_id == source.source_object_id
                         and proof.requirement_id == command.requirement_id
                         and proof.project_id == command.project_id
                         and proof.evidence_refs == tuple(sorted(source.evidence_refs)))
            else:
                proof = self._project_evidence.prove(tx, project_id=command.project_id,
                    evidence_id=source.source_object_id)
                valid = (type(proof) is EvidenceRequirementSourceProof
                         and proof.evidence_id == source.source_object_id
                         and proof.project_id == command.project_id
                         and source.evidence_refs == (source.source_object_id,))
            if not valid:
                raise RequirementVersionCreateError("REQUIREMENT_SOURCE_UNAVAILABLE")
            for evidence_id in source.evidence_refs:
                self._require_project_evidence(tx, command.project_id, evidence_id)
        for assessment in command.capability_assessments:
            proof = self._capability.prove(tx,
                baseline_version_id=assessment.baseline_version_id,
                capability_item_id=assessment.capability_item_id)
            if (type(proof) is not CapabilityRequirementSourceProof
                    or proof.baseline_version_id != assessment.baseline_version_id
                    or proof.capability_item_id != assessment.capability_item_id):
                raise RequirementVersionCreateError("REQUIREMENT_CAPABILITY_UNAVAILABLE")
            for ref in assessment.evidence_refs:
                if ref.evidence_role == "PROJECT":
                    self._require_project_evidence(tx, command.project_id, ref.evidence_id)
                else:
                    evidence = self._fixed_evidence.get_for_trace(
                        tx, scope="GLOBAL", project_id=None, evidence_id=ref.evidence_id,
                    )
                    if (type(evidence) is not LockedEvidenceSource
                            or evidence.scope != "GLOBAL" or evidence.project_id is not None):
                        raise RequirementVersionCreateError("REQUIREMENT_EVIDENCE_UNAVAILABLE")

    def _require_project_evidence(self, tx: object, project_id: uuid.UUID,
                                  evidence_id: uuid.UUID) -> None:
        proof = self._project_evidence.prove(
            tx, project_id=project_id, evidence_id=evidence_id,
        )
        if (type(proof) is not EvidenceRequirementSourceProof
                or proof.evidence_id != evidence_id):
            raise RequirementVersionCreateError("REQUIREMENT_EVIDENCE_UNAVAILABLE")

    @classmethod
    def _validate(cls, command: CreateRequirementVersion) -> dict[str, object]:
        if type(command) is not CreateRequirementVersion:
            raise RequirementVersionCreateError("VALIDATION_FAILED")
        identities = (command.trace_id, command.project_id, command.requirement_id)
        if (type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in identities)
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806
                or type(command.initial) is not bool
                or command.initial != (command.base_version_ref is None)
                or command.base_version_ref is not None and (
                    type(command.base_version_ref) is not uuid.UUID
                    or command.base_version_ref.int == 0)
                or command.priority not in _PRIORITIES or command.risk not in _RISKS
                or command.classification not in _CLASSIFICATIONS
                or not cls._text(command.statement, 16000)
                or not cls._text(command.rationale, 16000)
                or not cls._text(command.domain_name, 255)
                or command.title is not None and not cls._text(command.title, 500)
                or not cls._text(command.client_reason, 2000)
                or type(command.ai_task_refs) is not tuple or command.ai_task_refs):
            raise RequirementVersionCreateError("VALIDATION_FAILED")
        cls._tuple(command.sources, RequirementSourceDraft, 1, 200)
        cls._tuple(command.acceptance_criteria, RequirementAcceptanceDraft, 0, 500)
        cls._tuple(command.capability_assessments,
                   RequirementCapabilityAssessmentDraft, 0, 200)
        for values in (command.assumptions, command.exclusions, command.dependencies):
            if (type(values) is not tuple or len(values) > 500
                    or any(not cls._text(value, 4000) for value in values)):
                raise RequirementVersionCreateError("VALIDATION_FAILED")
        cls._validate_sources(command.sources)
        cls._validate_acceptance(command.acceptance_criteria)
        cls._validate_assessments(command.capability_assessments)
        return {
            "project_id": str(command.project_id),
            "requirement_id": str(command.requirement_id),
            "title": command.title, "statement": command.statement,
            "rationale": command.rationale, "domain_name": command.domain_name,
            "priority": command.priority, "risk": command.risk,
            "classification": command.classification,
            "sources": cls._jsonable(command.sources),
            "acceptance_criteria": cls._jsonable(command.acceptance_criteria),
            "capability_assessments": cls._jsonable(command.capability_assessments),
            "assumptions": list(command.assumptions),
            "exclusions": list(command.exclusions),
            "dependencies": list(command.dependencies),
            "ai_task_refs": [],
        }

    @classmethod
    def _validate_sources(cls, sources: tuple[RequirementSourceDraft, ...]) -> None:
        identities: set[tuple[str, uuid.UUID]] = set()
        for source in sources:
            key = (source.source_type, source.source_object_id)
            if (source.source_type not in _SOURCES
                    or type(source.source_object_id) is not uuid.UUID
                    or source.source_object_id.int == 0 or key in identities
                    or (source.source_type == "CONFIRMED_HANDOVER")
                       != (source.source_version_ref is not None)
                    or source.source_version_ref is not None and (
                        type(source.source_version_ref) is not uuid.UUID
                        or source.source_version_ref.int == 0)
                    or not cls._uuid_tuple(source.evidence_refs, 0, 100)
                    or source.source_type in {"HUMAN_DECISION", "PROJECT_EVIDENCE"}
                       and not source.evidence_refs):
                raise RequirementVersionCreateError("VALIDATION_FAILED")
            identities.add(key)

    @classmethod
    def _validate_acceptance(cls, values: tuple[RequirementAcceptanceDraft, ...]) -> None:
        for item in values:
            if any(not cls._text(value, 4000) for value in asdict(item).values()):
                raise RequirementVersionCreateError("VALIDATION_FAILED")

    @classmethod
    def _validate_assessments(
        cls, values: tuple[RequirementCapabilityAssessmentDraft, ...],
    ) -> None:
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for item in values:
            ids = (item.baseline_version_id, item.capability_item_id)
            roles = [ref.evidence_role for ref in item.evidence_refs]
            if (any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
                    or ids in seen or item.match_type not in _MATCHES
                    or item.assessor_kind != "HUMAN"
                    or item.confirmation_state not in _CONFIRMATIONS
                    or not cls._text(item.fit_gap, 4000)
                    or not cls._text(item.constraints_text, 4000)
                    or not cls._tuple(item.evidence_refs,
                                      RequirementAssessmentEvidenceDraft, 2, 200)
                    or set(roles) != {"STANDARD", "PROJECT"}
                    or len({ref.evidence_id for ref in item.evidence_refs})
                       != len(item.evidence_refs)
                    or any(type(ref.evidence_id) is not uuid.UUID
                           or ref.evidence_id.int == 0 for ref in item.evidence_refs)):
                raise RequirementVersionCreateError("VALIDATION_FAILED")
            seen.add(ids)

    @staticmethod
    def _tuple(value: object, item_type: type, minimum: int, maximum: int) -> bool:
        if (type(value) is not tuple or not minimum <= len(value) <= maximum
                or any(type(item) is not item_type for item in value)):
            raise RequirementVersionCreateError("VALIDATION_FAILED")
        return True

    @staticmethod
    def _uuid_tuple(value: object, minimum: int, maximum: int) -> bool:
        return (type(value) is tuple and minimum <= len(value) <= maximum
                and len(set(value)) == len(value)
                and all(type(item) is uuid.UUID and item.int != 0 for item in value))

    @staticmethod
    def _text(value: object, maximum: int) -> bool:
        return type(value) is str and 1 <= len(value) <= maximum and value == value.strip()

    @staticmethod
    def _jsonable(values: tuple[object, ...]) -> list[dict[str, object]]:
        def convert(value):
            if isinstance(value, uuid.UUID):
                return str(value)
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value
        return [convert(asdict(value)) for value in values]

    def _actor(self, tx: object, command: CreateRequirementVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementVersionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise RequirementVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
