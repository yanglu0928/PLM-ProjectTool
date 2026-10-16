"""Atomic immutable DRAFT SurveyVersion creation."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


_ANSWERS = frozenset({"TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "DATE", "NUMBER", "ATTACHMENT"})
_SOURCES = frozenset({"HANDOVER_ITEM", "CAPABILITY_ITEM", "TEMPLATE_DOCUMENT_VERSION", "MANUAL"})
_OPERATION = "V1_SURVEY_VERSION_CREATE"


def _jsonable(value: object) -> object:
    if type(value) is uuid.UUID:
        return str(value)
    if type(value) is dict:
        return {str(key): _jsonable(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_jsonable(item) for item in value]
    return value


class SurveyVersionCreateError(RuntimeError):
    def __init__(self, code: str = "SURVEY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyOptionDraft:
    option_code: str
    label: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class SurveySourceDraft:
    source_kind: str
    handover_item_row_id: uuid.UUID | None = None
    handover_analysis_version_id: uuid.UUID | None = None
    handover_analysis_id: uuid.UUID | None = None
    capability_item_row_id: uuid.UUID | None = None
    capability_baseline_version_id: uuid.UUID | None = None
    capability_baseline_id: uuid.UUID | None = None
    template_document_version_id: uuid.UUID | None = None
    template_document_id: uuid.UUID | None = None
    manual_source_note: str | None = None


@dataclass(frozen=True, slots=True)
class SurveyQuestionDraft:
    question_id: uuid.UUID
    topic: str
    question_text: str
    objective: str
    answer_type: str
    validation_rule: dict[str, object]
    required: bool
    condition_rule: dict[str, object] | None
    expected_output: str
    evidence_required: bool
    options: tuple[SurveyOptionDraft, ...]
    sources: tuple[SurveySourceDraft, ...]


@dataclass(frozen=True, slots=True)
class CreateSurveyVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    expected_lock_version: int
    questions: tuple[SurveyQuestionDraft, ...]
    target_department_ids: tuple[uuid.UUID, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SurveyLock:
    survey_id: uuid.UUID
    project_id: uuid.UUID
    survey_state: str
    current_approved_version_ref: uuid.UUID | None
    lock_version: int
    highest_version_no: int
    latest_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class CreatedSurveyVersion:
    survey_version_id: uuid.UUID
    survey_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    expected_lock_version: int
    lock_version: int


class SurveyVersionRepositoryPort(Protocol):
    def lock_survey(self, transaction: object, *, project_id: uuid.UUID,
                    survey_id: uuid.UUID) -> SurveyLock | None: ...
    def create(self, transaction: object, *, survey: SurveyLock,
               survey_version_id: uuid.UUID,
               questions: tuple[SurveyQuestionDraft, ...],
               target_department_ids: tuple[uuid.UUID, ...],
               content_fingerprint: bytes, actor_id: uuid.UUID) -> CreatedSurveyVersion: ...
    def initial_view(self, transaction: object, *, survey_version_id: uuid.UUID,
                     survey_id: uuid.UUID, project_id: uuid.UUID,
                     actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedSurveyVersion | None: ...


class SurveyVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 handover_sources: object, capability_sources: object,
                 template_sources: object, departments: object,
                 repository: SurveyVersionRepositoryPort, receipts: object,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, access, license_guard, authorization,
                        handover_sources, capability_sources, template_sources,
                        departments, repository, receipts, audit)
        if any(value is None for value in dependencies):
            raise ValueError("SurveyVersion dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._handover, self._capability = handover_sources, capability_sources
        self._templates, self._departments = template_sources, departments
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSurveyVersion) -> CreatedSurveyVersion:
        payload = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            content = canonical_payload_fingerprint(payload)
            request = canonical_payload_fingerprint({
                "content_fingerprint": content.hex(),
                "expected_lock_version": command.expected_lock_version,
            })
            version_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_VERSION_CREATE",
                )
                if authorized.user_id != actor or authorized.project_id != command.project_id:
                    raise SurveyVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=request)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyVersionCreateError()
                    result = self._repository.initial_view(
                        tx, survey_version_id=replay.ref_id, survey_id=command.survey_id,
                        project_id=command.project_id, actor_id=actor,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if (type(result) is not CreatedSurveyVersion
                            or not hmac.compare_digest(result.content_fingerprint, content)):
                        raise SurveyVersionCreateError()
                    return result
                survey = self._repository.lock_survey(
                    tx, project_id=command.project_id, survey_id=command.survey_id,
                )
                if type(survey) is not SurveyLock:
                    raise SurveyVersionCreateError("RESOURCE_NOT_FOUND")
                if survey.survey_state != "ACTIVE":
                    raise SurveyVersionCreateError("SURVEY_STATE_CONFLICT")
                if survey.lock_version != command.expected_lock_version:
                    raise SurveyVersionCreateError("CONFLICT_VERSION")
                self._prove_sources(tx, command)
                self._prove_departments(tx, command)
                result = self._repository.create(
                    tx, survey=survey, survey_version_id=version_id,
                    questions=command.questions,
                    target_department_ids=command.target_department_ids,
                    content_fingerprint=content, actor_id=actor,
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-02",
                    target_object_id=version_id, target_version_id=version_id,
                    after_state="DRAFT",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyVersionCreateError()
                self._receipts.complete(tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except SurveyVersionCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyVersionCreateError(error.code) from None
        except Exception:
            raise SurveyVersionCreateError() from None

    @classmethod
    def _validate(cls, command: CreateSurveyVersion) -> dict[str, object]:
        if (type(command) is not CreateSurveyVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in
                       (command.trace_id, command.project_id, command.survey_id))
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 9223372036854775807
                or type(command.questions) is not tuple or not 1 <= len(command.questions) <= 500
                or type(command.target_department_ids) is not tuple
                or not 1 <= len(command.target_department_ids) <= 200
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.target_department_ids)
                or len(set(command.target_department_ids)) != len(command.target_department_ids)):
            raise SurveyVersionCreateError("VALIDATION_FAILED")
        seen: set[uuid.UUID] = set()
        questions: list[dict[str, object]] = []
        for question in command.questions:
            cls._question(question, seen)
            seen.add(question.question_id)
            questions.append(_jsonable(asdict(question)))
        return {"project_id": str(command.project_id), "survey_id": str(command.survey_id),
                "questions": questions,
                "target_department_ids": [str(v) for v in command.target_department_ids]}

    @staticmethod
    def _question(q: SurveyQuestionDraft, seen: set[uuid.UUID]) -> None:
        text = lambda value, maximum: (type(value) is str and 1 <= len(value) <= maximum
                                       and value == value.strip())
        if (type(q) is not SurveyQuestionDraft or type(q.question_id) is not uuid.UUID
                or q.question_id.int == 0 or q.question_id in seen
                or not text(q.topic, 255) or not text(q.question_text, 4000)
                or not text(q.objective, 2000) or q.answer_type not in _ANSWERS
                or type(q.validation_rule) is not dict
                or type(q.required) is not bool
                or q.condition_rule is not None and type(q.condition_rule) is not dict
                or not text(q.expected_output, 2000)
                or type(q.evidence_required) is not bool
                or type(q.options) is not tuple or type(q.sources) is not tuple
                or not q.sources or len(q.sources) > 20
                or q.answer_type in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"} and len(q.options) < 2
                or q.answer_type not in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"} and q.options):
            raise SurveyVersionCreateError("VALIDATION_FAILED")
        codes: set[str] = set()
        for option in q.options:
            if (type(option) is not SurveyOptionDraft or not text(option.option_code, 32)
                    or not option.option_code[0].isalpha()
                    or option.option_code.upper() != option.option_code
                    or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in option.option_code)
                    or option.option_code in codes or not text(option.label, 255)
                    or option.description is not None and not text(option.description, 1000)):
                raise SurveyVersionCreateError("VALIDATION_FAILED")
            codes.add(option.option_code)
        for source in q.sources:
            SurveyVersionCreateService._source(source)

    @staticmethod
    def _source(s: SurveySourceDraft) -> None:
        if type(s) is not SurveySourceDraft or s.source_kind not in _SOURCES:
            raise SurveyVersionCreateError("VALIDATION_FAILED")
        groups = (
            (s.handover_item_row_id, s.handover_analysis_version_id, s.handover_analysis_id),
            (s.capability_item_row_id, s.capability_baseline_version_id, s.capability_baseline_id),
            (s.template_document_version_id, s.template_document_id),
        )
        expected = {"HANDOVER_ITEM": 0, "CAPABILITY_ITEM": 1,
                    "TEMPLATE_DOCUMENT_VERSION": 2}.get(s.source_kind)
        for index, group in enumerate(groups):
            present = any(value is not None for value in group)
            if present != (expected == index) or present and any(
                    type(value) is not uuid.UUID or value.int == 0 for value in group):
                raise SurveyVersionCreateError("VALIDATION_FAILED")
        manual = s.manual_source_note
        if s.source_kind == "MANUAL":
            if type(manual) is not str or not 1 <= len(manual) <= 2000 or manual != manual.strip():
                raise SurveyVersionCreateError("VALIDATION_FAILED")
        elif manual is not None:
            raise SurveyVersionCreateError("VALIDATION_FAILED")

    def _prove_sources(self, tx: object, command: CreateSurveyVersion) -> None:
        for question in command.questions:
            for source in question.sources:
                if source.source_kind == "HANDOVER_ITEM":
                    proof = self._handover.prove(tx, project_id=command.project_id,
                        analysis_item_row_id=source.handover_item_row_id,
                        handover_analysis_version_id=source.handover_analysis_version_id,
                        handover_analysis_id=source.handover_analysis_id)
                elif source.source_kind == "CAPABILITY_ITEM":
                    proof = self._capability.prove(tx,
                        capability_item_row_id=source.capability_item_row_id,
                        baseline_version_id=source.capability_baseline_version_id,
                        baseline_id=source.capability_baseline_id)
                elif source.source_kind == "TEMPLATE_DOCUMENT_VERSION":
                    proof = self._templates.prove(tx, path_project_id=command.project_id,
                        document_id=source.template_document_id,
                        document_version_id=source.template_document_version_id)
                else:
                    continue
                if proof is None:
                    raise SurveyVersionCreateError("SURVEY_SOURCE_UNAVAILABLE")

    def _prove_departments(self, tx: object, command: CreateSurveyVersion) -> None:
        for department_id in command.target_department_ids:
            if self._departments.prove(tx, project_id=command.project_id,
                                       department_id=department_id) is None:
                raise SurveyVersionCreateError("SURVEY_DEPARTMENT_UNAVAILABLE")

    def _actor(self, tx: object, command: CreateSurveyVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyVersionCreateError()
        actor = self._access.authenticated_user(tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
