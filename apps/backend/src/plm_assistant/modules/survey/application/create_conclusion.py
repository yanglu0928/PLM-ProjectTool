"""Authorized immutable SurveyConclusion draft creation."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

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
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)

from .conclusion_sources import (
    ConclusionProjectRecordProof, ConclusionProjectRecordQuery,
    ConclusionResponseProof, SurveyConclusionSourceError,
)
from .conclusion_views import SurveyConclusionView


_OPERATION = "V1_SURVEY_CONCLUSION_CREATE"


class SurveyConclusionCreateError(RuntimeError):
    def __init__(self, code: str = "SURVEY_CONCLUSION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DepartmentConclusionInput:
    department_id: uuid.UUID
    title: str
    statement: str
    response_refs: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleConclusionInput:
    module_key: str
    title: str
    statement: str
    response_refs: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ConclusionEvidenceInput:
    evidence_id: uuid.UUID
    reference_role: str


@dataclass(frozen=True, slots=True)
class ConclusionOpenIssueInput:
    action_item_id: uuid.UUID
    is_blocking: bool


@dataclass(frozen=True, slots=True)
class CreateSurveyConclusion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    round_refs: tuple[uuid.UUID, ...]
    department_conclusions: tuple[DepartmentConclusionInput, ...]
    module_conclusions: tuple[ModuleConclusionInput, ...]
    evidence_refs: tuple[ConclusionEvidenceInput, ...]
    open_issue_refs: tuple[ConclusionOpenIssueInput, ...]
    ai_task_refs: tuple[uuid.UUID, ...]
    supersedes_ref: uuid.UUID | None
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ConclusionCreatePlan:
    survey_conclusion_id: uuid.UUID
    conclusion_series_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    round_refs: tuple[uuid.UUID, ...]
    version_no: int
    supersedes_ref: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ConclusionCreateSnapshot:
    plan: ConclusionCreatePlan
    departments: tuple[DepartmentConclusionInput, ...]
    modules: tuple[ModuleConclusionInput, ...]
    evidence_inputs: tuple[ConclusionEvidenceInput, ...]
    issue_inputs: tuple[ConclusionOpenIssueInput, ...]
    response_proofs: tuple[ConclusionResponseProof, ...]
    evidence_proofs: tuple[ConclusionProjectRecordProof, ...]
    issue_proofs: tuple[SurveyConclusionIssueProof, ...]
    ai_proofs: tuple[SurveyConclusionAITaskProof, ...]
    content_fingerprint: bytes = field(repr=False)
    actor_id: uuid.UUID


class SurveyConclusionCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: object, response_owner: object, evidence_owner: object,
        issue_owner: object, ai_owner: object, receipts: object,
        audit: AuditService, clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository,
                response_owner, evidence_owner, issue_owner, ai_owner,
                receipts, audit)):
            raise ValueError("Survey Conclusion create dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._responses, self._evidence = response_owner, evidence_owner
        self._issues, self._ai = issue_owner, ai_owner
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSurveyConclusion) -> SurveyConclusionView:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            normalized = self._normalize(command)
            request_fingerprint = canonical_payload_fingerprint(
                self._request_payload(normalized),
            )
            conclusion_id = uuid.UUID(new_uuid7())
            proposed_series_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_CONCLUSION_CREATE",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_CONCLUSION_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
                    raise SurveyConclusionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyConclusionCreateError()
                    view = self._repository.get_initial(
                        tx, project_id=command.project_id,
                        survey_conclusion_id=replay.ref_id, actor_id=actor,
                    )
                    if not self._matches(view, normalized):
                        raise SurveyConclusionCreateError()
                    return view

                plan = self._repository.prepare(
                    tx, survey_conclusion_id=conclusion_id,
                    proposed_series_id=proposed_series_id,
                    project_id=command.project_id, survey_id=command.survey_id,
                    round_refs=normalized.round_refs,
                    supersedes_ref=command.supersedes_ref,
                )
                if (type(plan) is not ConclusionCreatePlan
                        or plan.survey_conclusion_id != conclusion_id
                        or plan.project_id != command.project_id
                        or plan.survey_id != command.survey_id
                        or plan.round_refs != normalized.round_refs
                        or plan.supersedes_ref != command.supersedes_ref
                        or type(plan.conclusion_series_id) is not uuid.UUID
                        or plan.conclusion_series_id.int == 0
                        or type(plan.version_no) is not int
                        or plan.version_no < 1
                        or (plan.version_no == 1)
                        != (plan.supersedes_ref is None)):
                    raise SurveyConclusionCreateError()

                responses = self._prove_responses(tx, normalized)
                issues = self._prove_issues(tx, normalized)
                evidence = self._prove_evidence(tx, normalized)
                ai_tasks = self._prove_ai(tx, normalized)
                content_fingerprint = canonical_payload_fingerprint(
                    self._snapshot_payload(
                        normalized, responses, evidence, issues, ai_tasks,
                    ),
                )
                snapshot = ConclusionCreateSnapshot(
                    plan=plan,
                    departments=normalized.department_conclusions,
                    modules=normalized.module_conclusions,
                    evidence_inputs=normalized.evidence_refs,
                    issue_inputs=normalized.open_issue_refs,
                    response_proofs=responses,
                    evidence_proofs=evidence,
                    issue_proofs=issues,
                    ai_proofs=ai_tasks,
                    content_fingerprint=content_fingerprint,
                    actor_id=actor,
                )
                view = self._repository.create(tx, snapshot)
                if (not self._matches(view, normalized)
                        or view.summary.survey_conclusion_id != conclusion_id
                        or view.summary.conclusion_series_id
                        != plan.conclusion_series_id
                        or view.summary.version_no != plan.version_no
                        or view.summary.content_fingerprint
                        != content_fingerprint.hex()
                        or view.summary.created_by != actor):
                    raise SurveyConclusionCreateError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_CONCLUSION_CREATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-05",
                    target_object_id=plan.conclusion_series_id,
                    target_version_id=conclusion_id, after_state="DRAFT",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyConclusionCreateError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, conclusion_id, 201,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except SurveyConclusionCreateError:
            raise
        except SurveyConclusionSourceError:
            raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID") from None
        except ProjectAuthorizationError as error:
            raise SurveyConclusionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyConclusionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyConclusionCreateError(error.code) from None
        except Exception:
            raise SurveyConclusionCreateError() from None

    def _actor(self, tx: object, command: CreateSurveyConclusion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyConclusionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyConclusionCreateError("AUTH_ACCESS_DENIED")
        return actor

    def _prove_responses(
        self, tx: object, command: CreateSurveyConclusion,
    ) -> tuple[ConclusionResponseProof, ...]:
        expected_departments = {
            response_id: item.department_id
            for item in command.department_conclusions
            for response_id in item.response_refs
        }
        ids = tuple(sorted({
            response_id
            for item in (*command.department_conclusions,
                         *command.module_conclusions)
            for response_id in item.response_refs
        }, key=lambda value: value.int))
        proofs: list[ConclusionResponseProof] = []
        for response_id in ids:
            proof = self._responses.prove(
                tx, project_id=command.project_id, survey_id=command.survey_id,
                round_refs=command.round_refs, response_id=response_id,
            )
            if (type(proof) is not ConclusionResponseProof
                    or proof.response_id != response_id
                    or proof.project_id != command.project_id
                    or proof.survey_id != command.survey_id
                    or proof.round_id not in command.round_refs
                    or type(proof.answer_fingerprint) is not bytes
                    or len(proof.answer_fingerprint) != 32
                    or type(proof.evidence_ids) is not tuple
                    or any(type(value) is not uuid.UUID or value.int == 0
                           for value in proof.evidence_ids)
                    or response_id in expected_departments
                    and proof.department_id != expected_departments[response_id]):
                raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID")
            proofs.append(proof)
        return tuple(proofs)

    def _prove_evidence(
        self, tx: object, command: CreateSurveyConclusion,
    ) -> tuple[ConclusionProjectRecordProof, ...]:
        query = ConclusionProjectRecordQuery(
            command.session_token, command.trace_id, command.project_id,
            command.evidence_refs[0].evidence_id,
        )
        proofs: list[ConclusionProjectRecordProof] = []
        for evidence_id in sorted(
                {item.evidence_id for item in command.evidence_refs},
                key=lambda value: value.int):
            proof = self._evidence.prove(
                tx, ConclusionProjectRecordQuery(
                    query.session_token, query.trace_id, query.project_id,
                    evidence_id,
                ),
            )
            if (type(proof) is not ConclusionProjectRecordProof
                    or proof.evidence_id != evidence_id
                    or proof.project_id != command.project_id
                    or type(proof.observed_evidence_lock_version) is not int
                    or proof.observed_evidence_lock_version < 0
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32):
                raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID")
            proofs.append(proof)
        return tuple(proofs)

    def _prove_issues(
        self, tx: object, command: CreateSurveyConclusion,
    ) -> tuple[SurveyConclusionIssueProof, ...]:
        proofs: list[SurveyConclusionIssueProof] = []
        for item in sorted(
                command.open_issue_refs,
                key=lambda value: value.action_item_id.int):
            proof = self._issues.prove(
                tx, project_id=command.project_id,
                action_item_id=item.action_item_id,
            )
            if (type(proof) is not SurveyConclusionIssueProof
                    or proof.action_item_id != item.action_item_id
                    or proof.project_id != command.project_id
                    or proof.action_state not in {
                        "OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED",
                        "CLOSED", "CANCELLED",
                    }
                    or type(proof.lock_version) is not int
                    or proof.lock_version < 0
                    or type(proof.updated_at) is not datetime
                    or proof.updated_at.tzinfo is None
                    or proof.updated_at.utcoffset() is None):
                raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID")
            proofs.append(proof)
        return tuple(proofs)

    def _prove_ai(
        self, tx: object, command: CreateSurveyConclusion,
    ) -> tuple[SurveyConclusionAITaskProof, ...]:
        proofs: list[SurveyConclusionAITaskProof] = []
        for ai_task_id in command.ai_task_refs:
            proof = self._ai.prove(
                tx, project_id=command.project_id, ai_task_id=ai_task_id,
            )
            if (type(proof) is not SurveyConclusionAITaskProof
                    or proof.ai_task_id != ai_task_id
                    or proof.project_id != command.project_id
                    or proof.fact_status != "NOT_FORMAL_FACT"
                    or proof.suggestion_state not in {
                        "AVAILABLE", "ACCEPTED_TO_DRAFT",
                    }
                    or any(type(value) is not uuid.UUID or value.int == 0
                           for value in (
                               proof.invocation_id, proof.suggestion_payload_id,
                           ))
                    or type(proof.payload_fingerprint) is not bytes
                    or len(proof.payload_fingerprint) != 32):
                raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID")
            proofs.append(proof)
        return tuple(proofs)

    @staticmethod
    def _validate(command: CreateSurveyConclusion) -> None:
        if (type(command) is not CreateSurveyConclusion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.survey_id,
                ))
                or command.supersedes_ref is not None and (
                    type(command.supersedes_ref) is not uuid.UUID
                    or command.supersedes_ref.int == 0)
                or not SurveyConclusionCreateService._uuid_tuple(
                    command.round_refs, minimum=1, maximum=100)
                or not SurveyConclusionCreateService._uuid_tuple(
                    command.ai_task_refs, minimum=0, maximum=100)
                or type(command.department_conclusions) is not tuple
                or type(command.module_conclusions) is not tuple
                or not 1 <= (len(command.department_conclusions)
                             + len(command.module_conclusions)) <= 1000
                or type(command.evidence_refs) is not tuple
                or not 1 <= len(command.evidence_refs) <= 1000
                or type(command.open_issue_refs) is not tuple
                or len(command.open_issue_refs) > 1000):
            raise SurveyConclusionCreateError("VALIDATION_FAILED")
        department_ids: set[uuid.UUID] = set()
        department_responses: set[uuid.UUID] = set()
        for item in command.department_conclusions:
            if (type(item) is not DepartmentConclusionInput
                    or type(item.department_id) is not uuid.UUID
                    or item.department_id.int == 0
                    or item.department_id in department_ids
                    or not SurveyConclusionCreateService._text(item.title, 255)
                    or not SurveyConclusionCreateService._text(item.statement, 20000)
                    or not SurveyConclusionCreateService._uuid_tuple(
                        item.response_refs, minimum=0, maximum=1000)
                    or department_responses.intersection(item.response_refs)):
                raise SurveyConclusionCreateError("VALIDATION_FAILED")
            department_ids.add(item.department_id)
            department_responses.update(item.response_refs)
        module_keys: set[str] = set()
        for item in command.module_conclusions:
            if (type(item) is not ModuleConclusionInput
                    or type(item.module_key) is not str
                    or re.fullmatch(r"[A-Z][A-Z0-9_.-]{0,63}",
                                    item.module_key) is None
                    or item.module_key in module_keys
                    or not SurveyConclusionCreateService._text(item.title, 255)
                    or not SurveyConclusionCreateService._text(item.statement, 20000)
                    or not SurveyConclusionCreateService._uuid_tuple(
                        item.response_refs, minimum=0, maximum=1000)):
                raise SurveyConclusionCreateError("VALIDATION_FAILED")
            module_keys.add(item.module_key)
        evidence_keys: set[tuple[uuid.UUID, str]] = set()
        for item in command.evidence_refs:
            key = (item.evidence_id, item.reference_role) if type(
                item) is ConclusionEvidenceInput else None
            if (type(item) is not ConclusionEvidenceInput
                    or type(item.evidence_id) is not uuid.UUID
                    or item.evidence_id.int == 0
                    or item.reference_role not in ("SUPPORT", "CONFLICT")
                    or key in evidence_keys):
                raise SurveyConclusionCreateError("VALIDATION_FAILED")
            evidence_keys.add(key)
        issue_ids: set[uuid.UUID] = set()
        for item in command.open_issue_refs:
            if (type(item) is not ConclusionOpenIssueInput
                    or type(item.action_item_id) is not uuid.UUID
                    or item.action_item_id.int == 0
                    or item.action_item_id in issue_ids
                    or type(item.is_blocking) is not bool):
                raise SurveyConclusionCreateError("VALIDATION_FAILED")
            issue_ids.add(item.action_item_id)

    @staticmethod
    def _normalize(command: CreateSurveyConclusion) -> CreateSurveyConclusion:
        sort_ids = lambda values: tuple(sorted(values, key=lambda value: value.int))
        return CreateSurveyConclusion(
            command.session_token, command.csrf_token, command.trace_id,
            command.project_id, command.survey_id, sort_ids(command.round_refs),
            tuple(DepartmentConclusionInput(
                item.department_id, item.title, item.statement,
                sort_ids(item.response_refs),
            ) for item in command.department_conclusions),
            tuple(ModuleConclusionInput(
                item.module_key, item.title, item.statement,
                sort_ids(item.response_refs),
            ) for item in command.module_conclusions),
            command.evidence_refs, command.open_issue_refs,
            sort_ids(command.ai_task_refs), command.supersedes_ref,
            command.idempotency_key,
        )

    @staticmethod
    def _request_payload(command: CreateSurveyConclusion) -> dict:
        return {
            "project_id": str(command.project_id),
            "survey_id": str(command.survey_id),
            "round_refs": [str(value) for value in command.round_refs],
            "departments": [{
                "department_id": str(item.department_id), "title": item.title,
                "statement": item.statement,
                "response_refs": [str(value) for value in item.response_refs],
            } for item in command.department_conclusions],
            "modules": [{
                "module_key": item.module_key, "title": item.title,
                "statement": item.statement,
                "response_refs": [str(value) for value in item.response_refs],
            } for item in command.module_conclusions],
            "evidence_refs": [{
                "evidence_id": str(item.evidence_id),
                "reference_role": item.reference_role,
            } for item in command.evidence_refs],
            "open_issue_refs": [{
                "action_item_id": str(item.action_item_id),
                "is_blocking": item.is_blocking,
            } for item in command.open_issue_refs],
            "ai_task_refs": [str(value) for value in command.ai_task_refs],
            "supersedes_ref": (
                None if command.supersedes_ref is None
                else str(command.supersedes_ref)
            ),
        }

    @classmethod
    def _snapshot_payload(cls, command, responses, evidence, issues, ai_tasks):
        payload = cls._request_payload(command)
        payload["response_proofs"] = [{
            "response_id": str(item.response_id),
            "answer_id": str(item.answer_id),
            "answer_fingerprint": item.answer_fingerprint.hex(),
        } for item in responses]
        payload["evidence_proofs"] = [{
            "evidence_id": str(item.evidence_id),
            "document_version_id": str(item.document_version_id),
            "lock_version": item.observed_evidence_lock_version,
            "content_fingerprint": item.content_fingerprint.hex(),
        } for item in evidence]
        payload["issue_proofs"] = [{
            "issue_id": str(item.action_item_id), "state": item.action_state,
            "lock_version": item.lock_version,
        } for item in issues]
        payload["ai_proofs"] = [{
            "ai_task_id": str(item.ai_task_id),
            "invocation_id": str(item.invocation_id),
            "suggestion_payload_id": str(item.suggestion_payload_id),
            "payload_fingerprint": item.payload_fingerprint.hex(),
        } for item in ai_tasks]
        return payload

    @classmethod
    def _matches(cls, view: object, command: CreateSurveyConclusion) -> bool:
        if type(view) is not SurveyConclusionView:
            return False
        summary = view.summary
        return (
            summary.project_id == command.project_id
            and summary.survey_id == command.survey_id
            and summary.round_refs == command.round_refs
            and summary.ai_task_refs == command.ai_task_refs
            and summary.supersedes_ref == command.supersedes_ref
            and summary.conclusion_state == "DRAFT"
            and summary.declared_department_count
            == len(command.department_conclusions)
            and summary.declared_module_count == len(command.module_conclusions)
            and summary.declared_evidence_count == len(command.evidence_refs)
            and summary.declared_open_issue_count == len(command.open_issue_refs)
            and tuple((item.department_id, item.title, item.statement,
                       item.response_refs) for item in view.department_conclusions)
            == tuple((item.department_id, item.title, item.statement,
                      item.response_refs) for item in command.department_conclusions)
            and tuple((item.module_key, item.title, item.statement,
                       item.response_refs) for item in view.module_conclusions)
            == tuple((item.module_key, item.title, item.statement,
                      item.response_refs) for item in command.module_conclusions)
            and tuple((item.evidence_id, item.reference_role)
                      for item in view.evidence_refs)
            == tuple((item.evidence_id, item.reference_role)
                     for item in command.evidence_refs)
            and tuple((item.issue_id, item.is_blocking)
                      for item in view.open_issue_refs)
            == tuple((item.action_item_id, item.is_blocking)
                     for item in command.open_issue_refs)
        )

    @staticmethod
    def _uuid_tuple(values: object, *, minimum: int, maximum: int) -> bool:
        return (type(values) is tuple and minimum <= len(values) <= maximum
                and len(set(values)) == len(values)
                and all(type(value) is uuid.UUID and value.int != 0
                        for value in values))

    @staticmethod
    def _text(value: object, maximum: int) -> bool:
        return (type(value) is str and 1 <= len(value) <= maximum
                and value == value.strip())
