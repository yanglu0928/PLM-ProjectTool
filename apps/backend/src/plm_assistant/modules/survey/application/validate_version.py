"""Idempotent, current-fact validation for an immutable SurveyVersion."""

from __future__ import annotations

import hmac
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.capability.application.survey_source_proof import CapabilitySurveySourceProof
from plm_assistant.modules.document.application.survey_template_proof import SurveyTemplateProof
from plm_assistant.modules.handover.application.survey_source_proof import HandoverSurveySourceProof
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.survey_source_proof import SurveyTargetDepartmentProof

from .condition_rules import SurveyConditionLeaf, SurveyConditionRuleError, parse_condition_rule
from .create_version import SurveyQuestionDraft, SurveySourceDraft, SurveyVersionCreateService, _jsonable


_ORDER = (
    "CONTENT_FINGERPRINT_MISMATCH", "COUNT_MISMATCH",
    "QUESTION_RULE_INVALID", "CONDITION_RULE_INVALID",
    "CONDITION_REFERENCE_INVALID", "CONDITION_CYCLE",
    "SOURCE_UNAVAILABLE", "TARGET_DEPARTMENT_UNAVAILABLE",
)
_LETTERS = dict(zip(_ORDER, "FCQRLYSD", strict=True))
_BY_LETTER = {value: key for key, value in _LETTERS.items()}
_OPERATION = "V1_SURVEY_VERSION_VALIDATE"


class SurveyVersionValidationError(RuntimeError):
    def __init__(self, code: str = "SURVEY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidateSurveyVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SurveyVersionSnapshot:
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    declared_question_count: int
    declared_option_count: int
    declared_source_count: int
    declared_target_department_count: int
    questions: tuple[SurveyQuestionDraft, ...]
    target_department_ids: tuple[uuid.UUID, ...]
    ordinals_contiguous: bool


@dataclass(frozen=True, slots=True)
class SurveyValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str


@dataclass(frozen=True, slots=True)
class SurveyVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    question_count: int
    option_count: int
    source_count: int
    target_department_count: int
    conditional_question_count: int
    valid: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime


class SurveyVersionValidationRepositoryPort(Protocol):
    def lock_snapshot(self, transaction: object, *, project_id: uuid.UUID,
                      survey_id: uuid.UUID,
                      survey_version_id: uuid.UUID) -> SurveyVersionSnapshot | None: ...


class SurveyValidationAuditPort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            survey_version_id: uuid.UUID) -> SurveyValidationAudit | None: ...


class SurveyVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 handover_sources: object, capability_sources: object,
                 template_sources: object, departments: object,
                 repository: SurveyVersionValidationRepositoryPort,
                 audit_source: SurveyValidationAuditPort, receipts: object,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, access, license_guard, authorization,
                        handover_sources, capability_sources, template_sources,
                        departments, repository, audit_source, receipts, audit)
        if any(value is None for value in dependencies):
            raise ValueError("Survey validation dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._handover, self._capability = handover_sources, capability_sources
        self._templates, self._departments = template_sources, departments
        self._repository, self._audit_source = repository, audit_source
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidateSurveyVersion) -> SurveyVersionValidationReport:
        if (type(command) is not ValidateSurveyVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.survey_id,
                    command.survey_version_id))):
            raise SurveyVersionValidationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            request = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_id": str(command.survey_id),
                "survey_version_id": str(command.survey_version_id),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_VERSION_VALIDATE",
                )
                if authorized.user_id != actor or authorized.project_id != command.project_id:
                    raise SurveyVersionValidationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=request)
                snapshot = self._repository.lock_snapshot(
                    tx, project_id=command.project_id, survey_id=command.survey_id,
                    survey_version_id=command.survey_version_id,
                )
                if type(snapshot) is not SurveyVersionSnapshot:
                    raise SurveyVersionValidationError("RESOURCE_NOT_FOUND")
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise SurveyVersionValidationError()
                    proof = self._audit_source.get(
                        tx, audit_event_id=replay.ref_id, actor_id=actor,
                        project_id=command.project_id,
                        survey_version_id=command.survey_version_id,
                    )
                    if type(proof) is not SurveyValidationAudit:
                        raise SurveyVersionValidationError()
                    return self._report(snapshot, proof)
                issues = self._current_issues(tx, snapshot)
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_VERSION_VALIDATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-02",
                    target_object_id=command.survey_version_id,
                    target_version_id=command.survey_version_id,
                    reason_code=self._reason(issues),
                    before_state=snapshot.version_state, after_state=snapshot.version_state,
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyVersionValidationError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, audit_id, 200,
                ))
                proof = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    survey_version_id=command.survey_version_id,
                )
                if type(proof) is not SurveyValidationAudit:
                    raise SurveyVersionValidationError()
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return self._report(snapshot, proof)
        except SurveyVersionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyVersionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyVersionValidationError(error.code) from None
        except Exception:
            raise SurveyVersionValidationError() from None

    def _current_issues(self, tx: object,
                        snapshot: SurveyVersionSnapshot) -> tuple[str, ...]:
        found: set[str] = set()
        if not hmac.compare_digest(
                canonical_payload_fingerprint(self._snapshot_payload(snapshot)),
                snapshot.content_fingerprint):
            found.add("CONTENT_FINGERPRINT_MISMATCH")
        option_count = sum(len(question.options) for question in snapshot.questions)
        source_count = sum(len(question.sources) for question in snapshot.questions)
        if (not snapshot.ordinals_contiguous
                or snapshot.declared_question_count != len(snapshot.questions)
                or snapshot.declared_option_count != option_count
                or snapshot.declared_source_count != source_count
                or snapshot.declared_target_department_count
                != len(snapshot.target_department_ids)):
            found.add("COUNT_MISMATCH")
        self._question_issues(snapshot, found)
        self._source_issues(tx, snapshot, found)
        return tuple(code for code in _ORDER if code in found)

    @classmethod
    def _question_issues(cls, snapshot: SurveyVersionSnapshot,
                         found: set[str]) -> None:
        seen: set[uuid.UUID] = set()
        questions = {question.question_id: question for question in snapshot.questions}
        position = {question.question_id: index
                    for index, question in enumerate(snapshot.questions)}
        graph: dict[uuid.UUID, set[uuid.UUID]] = {
            question.question_id: set() for question in snapshot.questions
        }
        for index, question in enumerate(snapshot.questions):
            try:
                SurveyVersionCreateService._question(question, seen)
                if not cls._answer_rule_valid(question):
                    raise ValueError("answer rule")
            except Exception:
                found.add("QUESTION_RULE_INVALID")
            seen.add(question.question_id)
            if question.condition_rule is None:
                continue
            try:
                leaves = parse_condition_rule(question.condition_rule)
            except SurveyConditionRuleError:
                found.add("CONDITION_RULE_INVALID")
                continue
            for leaf in leaves:
                graph[question.question_id].add(leaf.question_ref)
                referenced = questions.get(leaf.question_ref)
                if (referenced is None or position[leaf.question_ref] >= index):
                    found.add("CONDITION_REFERENCE_INVALID")
                elif not cls._condition_value_valid(leaf, referenced):
                    found.add("CONDITION_RULE_INVALID")
        if cls._has_cycle(graph):
            found.add("CONDITION_CYCLE")

    def _source_issues(self, tx: object, snapshot: SurveyVersionSnapshot,
                       found: set[str]) -> None:
        for question in snapshot.questions:
            for source in question.sources:
                if not self._source_current(tx, snapshot.project_id, source):
                    found.add("SOURCE_UNAVAILABLE")
        for department_id in snapshot.target_department_ids:
            proof = self._departments.prove(
                tx, project_id=snapshot.project_id, department_id=department_id,
            )
            if (type(proof) is not SurveyTargetDepartmentProof
                    or proof.department_id != department_id
                    or proof.project_id != snapshot.project_id or proof.state != "ACTIVE"):
                found.add("TARGET_DEPARTMENT_UNAVAILABLE")

    def _source_current(self, tx: object, project_id: uuid.UUID,
                        source: SurveySourceDraft) -> bool:
        if source.source_kind == "MANUAL":
            return True
        if source.source_kind == "HANDOVER_ITEM":
            proof = self._handover.prove(
                tx, project_id=project_id,
                analysis_item_row_id=source.handover_item_row_id,
                handover_analysis_version_id=source.handover_analysis_version_id,
                handover_analysis_id=source.handover_analysis_id,
            )
            return (type(proof) is HandoverSurveySourceProof
                    and proof.analysis_item_row_id == source.handover_item_row_id
                    and proof.handover_analysis_version_id
                    == source.handover_analysis_version_id
                    and proof.handover_analysis_id == source.handover_analysis_id
                    and proof.project_id == project_id
                    and proof.item_state in {"CONFIRMED", "RESOLVED", "ACCEPTED_RISK"})
        if source.source_kind == "CAPABILITY_ITEM":
            proof = self._capability.prove(
                tx, capability_item_row_id=source.capability_item_row_id,
                baseline_version_id=source.capability_baseline_version_id,
                baseline_id=source.capability_baseline_id,
            )
            return (type(proof) is CapabilitySurveySourceProof
                    and proof.capability_item_row_id == source.capability_item_row_id
                    and proof.baseline_version_id == source.capability_baseline_version_id
                    and proof.baseline_id == source.capability_baseline_id
                    and proof.item_state == "AVAILABLE")
        if source.source_kind == "TEMPLATE_DOCUMENT_VERSION":
            proof = self._templates.prove(
                tx, path_project_id=project_id,
                document_id=source.template_document_id,
                document_version_id=source.template_document_version_id,
            )
            return (type(proof) is SurveyTemplateProof
                    and proof.document_version_id == source.template_document_version_id
                    and proof.document_id == source.template_document_id
                    and (proof.scope == "GLOBAL" and proof.project_id is None
                         or proof.scope == "PROJECT" and proof.project_id == project_id))
        return False

    @staticmethod
    def _snapshot_payload(snapshot: SurveyVersionSnapshot) -> dict[str, object]:
        return {
            "project_id": str(snapshot.project_id),
            "survey_id": str(snapshot.survey_id),
            "questions": [_jsonable(asdict(question))
                          for question in snapshot.questions],
            "target_department_ids": [str(value)
                                      for value in snapshot.target_department_ids],
        }

    @staticmethod
    def _answer_rule_valid(question: SurveyQuestionDraft) -> bool:
        rule = question.validation_rule
        if type(rule) is not dict:
            return False
        answer_type = question.answer_type
        if answer_type == "TEXT":
            if not set(rule) <= {"min_length", "max_length"}:
                return False
            minimum, maximum = rule.get("min_length", 0), rule.get("max_length", 4000)
            return (type(minimum) is int and type(maximum) is int
                    and 0 <= minimum <= maximum <= 4000)
        if answer_type == "NUMBER":
            if not set(rule) <= {"minimum", "maximum", "integer"}:
                return False
            minimum, maximum = rule.get("minimum"), rule.get("maximum")
            numeric = lambda value: value is None or (
                type(value) in (int, float) and not isinstance(value, bool))
            return (numeric(minimum) and numeric(maximum)
                    and (minimum is None or maximum is None or minimum <= maximum)
                    and type(rule.get("integer", False)) is bool)
        if answer_type == "DATE":
            if not set(rule) <= {"minimum", "maximum"}:
                return False
            try:
                minimum = None if rule.get("minimum") is None else date.fromisoformat(rule["minimum"])
                maximum = None if rule.get("maximum") is None else date.fromisoformat(rule["maximum"])
            except (TypeError, ValueError):
                return False
            return minimum is None or maximum is None or minimum <= maximum
        if answer_type == "MULTIPLE_CHOICE":
            if not set(rule) <= {"min_selections", "max_selections"}:
                return False
            minimum, maximum = rule.get("min_selections", 0), rule.get(
                "max_selections", len(question.options))
            return (type(minimum) is int and type(maximum) is int
                    and 0 <= minimum <= maximum <= len(question.options))
        if answer_type == "ATTACHMENT":
            if not set(rule) <= {"min_files", "max_files", "allowed_extensions"}:
                return False
            minimum, maximum = rule.get("min_files", 0), rule.get("max_files", 20)
            extensions = rule.get("allowed_extensions", [])
            return (type(minimum) is int and type(maximum) is int
                    and 0 <= minimum <= maximum <= 20 and type(extensions) is list
                    and len(extensions) <= 50 and len(set(extensions)) == len(extensions)
                    and all(type(value) is str
                            and re.fullmatch(r"\.[a-z0-9]{1,16}", value)
                            for value in extensions))
        return answer_type == "SINGLE_CHOICE" and not rule

    @staticmethod
    def _condition_value_valid(leaf: SurveyConditionLeaf,
                               referenced: SurveyQuestionDraft) -> bool:
        if not leaf.has_value:
            return True
        values = leaf.value if type(leaf.value) is list else [leaf.value]
        if referenced.answer_type in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
            allowed = {option.option_code for option in referenced.options}
            return all(type(value) is str and value in allowed for value in values)
        if referenced.answer_type == "NUMBER":
            return all(type(value) in (int, float) and not isinstance(value, bool)
                       for value in values)
        if referenced.answer_type == "DATE":
            try:
                return all(type(value) is str and date.fromisoformat(value)
                           for value in values)
            except ValueError:
                return False
        if referenced.answer_type == "TEXT":
            return all(type(value) is str for value in values)
        return False

    @staticmethod
    def _has_cycle(graph: dict[uuid.UUID, set[uuid.UUID]]) -> bool:
        visiting: set[uuid.UUID] = set()
        complete: set[uuid.UUID] = set()

        def visit(node: uuid.UUID) -> bool:
            if node in visiting:
                return True
            if node in complete or node not in graph:
                return False
            visiting.add(node)
            if any(visit(target) for target in graph[node]):
                return True
            visiting.remove(node)
            complete.add(node)
            return False

        return any(visit(node) for node in graph)

    @staticmethod
    def _reason(issues: tuple[str, ...]) -> str:
        return ("SURVEY_VALIDATION_PASSED" if not issues else
                "SURVEY_VALIDATION_FAILED_" + "".join(_LETTERS[issue] for issue in issues))

    @staticmethod
    def _issues(reason: str) -> tuple[str, ...]:
        if reason == "SURVEY_VALIDATION_PASSED":
            return ()
        prefix = "SURVEY_VALIDATION_FAILED_"
        if not reason.startswith(prefix):
            raise SurveyVersionValidationError()
        try:
            issues = tuple(_BY_LETTER[value] for value in reason[len(prefix):])
        except KeyError:
            raise SurveyVersionValidationError() from None
        if tuple(code for code in _ORDER if code in issues) != issues:
            raise SurveyVersionValidationError()
        return issues

    @staticmethod
    def _report(snapshot: SurveyVersionSnapshot,
                proof: SurveyValidationAudit) -> SurveyVersionValidationReport:
        issues = SurveyVersionValidationService._issues(proof.reason_code)
        return SurveyVersionValidationReport(
            proof.audit_event_id, proof.trace_id, snapshot.survey_id,
            snapshot.survey_version_id, snapshot.project_id, snapshot.version_no,
            snapshot.version_state, len(snapshot.questions),
            sum(len(question.options) for question in snapshot.questions),
            sum(len(question.sources) for question in snapshot.questions),
            len(snapshot.target_department_ids),
            sum(question.condition_rule is not None for question in snapshot.questions),
            not issues, issues, proof.observed_at,
        )

    def _actor(self, tx: object, command: ValidateSurveyVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyVersionValidationError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyVersionValidationError("AUTH_ACCESS_DENIED")
        return actor
