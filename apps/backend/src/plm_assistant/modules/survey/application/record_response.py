"""Authorized atomic append of one Survey Response, Answer and Evidence set."""

from __future__ import annotations

import math
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, EvidenceFixedSourceError, VerifiedProjectEvidence,
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
from plm_assistant.modules.survey.application.round_source import (
    SurveyRoundSourceAppend, SurveyRoundSourceError, SurveyRoundSourceQuery,
    SurveyRoundSourceRecord, VerifiedRoundProjectRecord,
)

from .response_views import (
    FixedAnswerEvidence, SurveyResponseContext, SurveyResponseWriteView,
)


_OPERATION = "V1_SURVEY_RESPONSE_RECORD"


class SurveyResponseRecordError(RuntimeError):
    def __init__(self, code: str = "SURVEY_RESPONSE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RecordSurveyResponse:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_assignment_id: uuid.UUID
    question_id: uuid.UUID
    expected_lock_version: int
    response_source: str
    raw_answer: str | None
    answer_value: object | None
    evidence_ids: tuple[uuid.UUID, ...]
    project_record_evidence_id: uuid.UUID | None
    correction_of_response_id: uuid.UUID | None
    idempotency_key: str = field(repr=False)


class SurveyResponseRecordService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: object, receipts: object, audit: AuditService,
        evidence_owner: object, round_record_proof: object,
        round_source_repository: object,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository,
                receipts, audit, evidence_owner, round_record_proof,
                round_source_repository)):
            raise ValueError("Survey Response record dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._evidence, self._round_proof = evidence_owner, round_record_proof
        self._round_sources = round_source_repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def record(self, command: RecordSurveyResponse) -> SurveyResponseWriteView:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_round_id": str(command.survey_round_id),
                "survey_assignment_id": str(command.survey_assignment_id),
                "question_id": str(command.question_id),
                "expected_lock_version": command.expected_lock_version,
                "response_source": command.response_source,
                "raw_answer": command.raw_answer,
                "answer_value": command.answer_value,
                "evidence_ids": [str(value) for value in command.evidence_ids],
                "project_record_evidence_id": (
                    None if command.project_record_evidence_id is None
                    else str(command.project_record_evidence_id)),
                "correction_of_response_id": (
                    None if command.correction_of_response_id is None
                    else str(command.correction_of_response_id)),
            })
            response_id, answer_id = uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_RESPONSE_RECORD",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_RESPONSE_RECORD"):
                    raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyResponseRecordError()
                    result = self._repository.get_written(
                        tx, project_id=command.project_id,
                        survey_response_id=replay.ref_id, actor_id=actor)
                    if not self._matches(result, command, replay.ref_id, actor):
                        raise SurveyResponseRecordError()
                    return result
                context = self._repository.lock_context(
                    tx, project_id=command.project_id,
                    survey_round_id=command.survey_round_id,
                    survey_assignment_id=command.survey_assignment_id,
                    question_id=command.question_id,
                    expected_lock_version=command.expected_lock_version,
                    actor_id=actor, actor_role=authorized.project_role,
                    response_source=command.response_source)
                if type(context) is not SurveyResponseContext:
                    raise SurveyResponseRecordError()
                occurred_at = self._now()
                source_record = self._facilitated_source(
                    tx, command, context, authorized.project_role, occurred_at)
                evidence = self._fixed_evidence(
                    tx, command, actor, source_record)
                raw, value = self._answer(context, command, evidence)
                result = self._repository.append(
                    tx, context=context, survey_response_id=response_id,
                    survey_answer_id=answer_id,
                    response_source=command.response_source,
                    round_source_record_ref_id=(None if source_record is None else
                                                source_record.round_source_record_ref_id),
                    correction_of_response_id=command.correction_of_response_id,
                    raw_answer=raw, answer_value=value, evidence=evidence,
                    actor_id=actor, recorded_at=occurred_at)
                if not self._matches(result, command, response_id, actor):
                    raise SurveyResponseRecordError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_RESPONSE_RECORDED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-04",
                    target_object_id=command.survey_assignment_id,
                    target_version_id=context.survey_version_id,
                    reason_code=command.response_source,
                    before_state=context.before_state, after_state="IN_PROGRESS"))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyResponseRecordError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, response_id, 201))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except SurveyResponseRecordError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyResponseRecordError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyResponseRecordError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyResponseRecordError(error.code) from None
        except (EvidenceFixedSourceError, SurveyRoundSourceError) as error:
            code = getattr(error, "code", "SURVEY_RESPONSE_UNAVAILABLE")
            if code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED",
                        "RESOURCE_NOT_FOUND", "EVIDENCE_FINGERPRINT_MISMATCH"):
                raise SurveyResponseRecordError(code) from None
            raise SurveyResponseRecordError() from None
        except Exception:
            raise SurveyResponseRecordError() from None

    def _facilitated_source(self, tx, command, context, role, occurred_at):
        if command.response_source == "SELF_SERVICE":
            return None
        if role != "IMPLEMENTATION_MEMBER":
            raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
        proof = self._round_proof.prove(tx, SurveyRoundSourceQuery(
            command.session_token, command.trace_id, command.project_id,
            command.project_record_evidence_id))
        if type(proof) is not VerifiedRoundProjectRecord or proof.recorded_by is None:
            raise SurveyResponseRecordError()
        record = self._round_sources.append(tx, SurveyRoundSourceAppend(
            context.survey_round_id, context.project_id, context.question_id,
            proof, occurred_at))
        if (type(record) is not SurveyRoundSourceRecord
                or record.survey_round_id != context.survey_round_id
                or record.question_id != context.question_id):
            raise SurveyResponseRecordError()
        return record

    def _fixed_evidence(self, tx, command, actor, source_record):
        requested = list(command.evidence_ids)
        if source_record is not None and source_record.evidence_id not in requested:
            requested.insert(0, source_record.evidence_id)
        results = []
        for evidence_id in requested:
            if source_record is not None and evidence_id == source_record.evidence_id:
                proof = FixedAnswerEvidence(
                    source_record.evidence_id, source_record.document_id,
                    source_record.document_version_id,
                    source_record.observed_evidence_lock_version,
                    source_record.content_fingerprint, actor)
            else:
                fixed = self._evidence.prove(
                    tx, EvidenceFixedProjectQuery(
                        command.session_token, command.trace_id, command.project_id),
                    evidence_id)
                if (type(fixed) is not VerifiedProjectEvidence
                        or fixed.project_id != command.project_id
                        or fixed.evidence_id != evidence_id
                        or fixed.verified_by != actor
                        or fixed.scope != "PROJECT"
                        or fixed.observed_state != "ELIGIBLE"
                        or fixed.document_category == "TEMPLATE"):
                    raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
                proof = FixedAnswerEvidence(
                    fixed.evidence_id, fixed.document_id, fixed.document_version_id,
                    fixed.observed_lock_version, fixed.content_fingerprint, actor)
            results.append(proof)
        return tuple(results)

    def _answer(self, context, command, evidence):
        raw = self._text(command.raw_answer, 20000, optional=True)
        value = command.answer_value
        if context.answer_type == "TEXT":
            value = self._text(value, 20000, optional=False)
        elif context.answer_type == "SINGLE_CHOICE":
            if type(value) is not str or value not in context.option_codes:
                raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
        elif context.answer_type == "MULTIPLE_CHOICE":
            if (type(value) not in (list, tuple) or not value
                    or any(type(item) is not str or item not in context.option_codes
                           for item in value)
                    or len(set(value)) != len(value)):
                raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
            value = list(value)
        elif context.answer_type == "DATE":
            if type(value) is not str:
                raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
            try: value = date.fromisoformat(value).isoformat()
            except ValueError: raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID") from None
        elif context.answer_type == "NUMBER":
            if (type(value) not in (int, float)
                    or type(value) is float and not math.isfinite(value)):
                raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
        elif context.answer_type == "ATTACHMENT":
            if value is not None or not evidence:
                raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
            value = [str(item.evidence_id) for item in evidence]
        else:
            raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
        return raw, value

    def _actor(self, tx, command):
        now = self._now()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now)
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyResponseRecordError("AUTH_ACCESS_DENIED")
        return actor

    def _now(self):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyResponseRecordError()
        return now.astimezone(timezone.utc)

    @staticmethod
    def _validate(command):
        if (type(command) is not RecordSurveyResponse
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.survey_round_id,
                    command.survey_assignment_id, command.question_id))
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 2**63 - 1
                or command.response_source not in ("SELF_SERVICE", "FACILITATED_RECORD")
                or type(command.evidence_ids) is not tuple
                or len(command.evidence_ids) > 50
                or len(set(command.evidence_ids)) != len(command.evidence_ids)
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.evidence_ids)
                or command.correction_of_response_id is not None and (
                    type(command.correction_of_response_id) is not uuid.UUID
                    or command.correction_of_response_id.int == 0)
                or (command.response_source == "SELF_SERVICE"
                    and command.project_record_evidence_id is not None)
                or (command.response_source == "FACILITATED_RECORD"
                    and (type(command.project_record_evidence_id) is not uuid.UUID
                         or command.project_record_evidence_id.int == 0))):
            raise SurveyResponseRecordError("VALIDATION_FAILED")

    @staticmethod
    def _text(value, maximum, *, optional):
        if value is None and optional: return None
        if type(value) is not str:
            raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= maximum
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise SurveyResponseRecordError("SURVEY_RESPONSE_INVALID")
        return result

    @staticmethod
    def _matches(view, command, response_id, actor):
        expected_evidence = len(command.evidence_ids)
        if (command.response_source == "FACILITATED_RECORD"
                and command.project_record_evidence_id not in command.evidence_ids):
            expected_evidence += 1
        return (type(view) is SurveyResponseWriteView
                and view.survey_response_id == response_id
                and view.survey_assignment_id == command.survey_assignment_id
                and view.survey_round_id == command.survey_round_id
                and view.project_id == command.project_id
                and view.question_id == command.question_id
                and view.response_source == command.response_source
                and view.recorded_by == actor
                and view.evidence_count == expected_evidence
                and ((command.response_source == "SELF_SERVICE"
                      and view.round_source_record_ref_id is None)
                     or (command.response_source == "FACILITATED_RECORD"
                         and type(view.round_source_record_ref_id) is uuid.UUID
                         and view.round_source_record_ref_id.int != 0))
                and view.correction_of_response_id == command.correction_of_response_id
                and view.assignment_state == "IN_PROGRESS"
                and view.assignment_etag == f'"v{command.expected_lock_version + 1}"')
