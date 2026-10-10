"""Authorized VALIDATE and RETURN transitions for submitted Survey Assignments."""

from __future__ import annotations

import hmac
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectQuery, EvidenceFixedSourceError, VerifiedProjectEvidence
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError, IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint, validate_idempotency_key
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError

from .submission_completeness import SurveySubmissionIncomplete, evaluate_submission
from .submission_views import SurveyAssignmentReviewReceipt, SurveyAssignmentSubmissionSnapshot


class SurveyAssignmentReviewError(RuntimeError):
    def __init__(self, code="SURVEY_ASSIGNMENT_UNAVAILABLE"):
        self.code = code; super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviewSurveyAssignment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_assignment_id: uuid.UUID
    expected_lock_version: int
    return_comment: str | None
    idempotency_key: str = field(repr=False)


class SurveyAssignmentReviewService:
    def __init__(self, *, unit_of_work, access, license_guard, authorization,
                 repository, receipts, audit, evidence_owner, clock):
        if any(item is None for item in (unit_of_work, access, license_guard,
                authorization, repository, receipts, audit, evidence_owner, clock)):
            raise ValueError("Survey Assignment review dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit, self._evidence, self._clock = receipts, audit, evidence_owner, clock

    def validate(self, command): return self._execute(command, "VALIDATED")
    def return_assignment(self, command): return self._execute(command, "RETURNED")

    def _execute(self, command, target):
        comment = self._validate(command, target)
        operation = "SURVEY_ASSIGNMENT_" + ("VALIDATE" if target == "VALIDATED" else "RETURN")
        receipt_operation = "V1_" + operation
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "survey_round_id": str(command.survey_round_id),
                "survey_assignment_id": str(command.survey_assignment_id),
                "expected_lock_version": command.expected_lock_version, "return_comment": comment})
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise SurveyAssignmentReviewError()
                now = now.astimezone(timezone.utc)
                actor = self._access.authenticated_user(tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now)
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveyAssignmentReviewError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id, operation=operation)
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor or authorized.project_id != command.project_id
                        or authorized.operation != operation):
                    raise SurveyAssignmentReviewError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(actor_id=actor, project_id=command.project_id,
                                                   operation=receipt_operation, key=command.idempotency_key)
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != receipt_operation or replay.ref_id != command.survey_assignment_id or replay.status_code != 200:
                        raise SurveyAssignmentReviewError()
                    result = self._repository.replay_review(tx, project_id=command.project_id,
                        survey_round_id=command.survey_round_id, survey_assignment_id=command.survey_assignment_id,
                        actor_id=actor, actor_role=authorized.project_role, target_state=target,
                        result_version=command.expected_lock_version + 1, return_comment=comment)
                    if not self._matches(result, command, target, comment): raise SurveyAssignmentReviewError()
                    return result
                snapshot = self._repository.lock_snapshot(tx, project_id=command.project_id,
                    survey_round_id=command.survey_round_id, survey_assignment_id=command.survey_assignment_id,
                    expected_lock_version=command.expected_lock_version, actor_id=actor,
                    actor_role=authorized.project_role, required_state="SUBMITTED", manager_access=True)
                if type(snapshot) is not SurveyAssignmentSubmissionSnapshot: raise SurveyAssignmentReviewError("RESOURCE_NOT_FOUND")
                if target == "VALIDATED": evaluate_submission(snapshot, self._evidence_names(tx, command, snapshot))
                result = self._repository.review_transition(tx, snapshot=snapshot, actor_id=actor,
                                                             target_state=target, return_comment=comment)
                if not self._matches(result, command, target, comment): raise SurveyAssignmentReviewError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT", target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_ASSIGNMENT_" + target, outcome="SUCCESS", target_owner_module="survey",
                    target_object_type="SRV-04", target_object_id=command.survey_assignment_id,
                    target_version_id=snapshot.survey_version_id, reason_code=None,
                    before_state="SUBMITTED", after_state=target))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyAssignmentReviewError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(receipt_operation, command.survey_assignment_id, 200))
                self._guard.require_valid(trace_id=command.trace_id); tx.commit(); return result
        except SurveyAssignmentReviewError: raise
        except SurveySubmissionIncomplete: raise SurveyAssignmentReviewError("SURVEY_ASSIGNMENT_INCOMPLETE") from None
        except EvidenceFixedSourceError: raise SurveyAssignmentReviewError("SURVEY_ASSIGNMENT_INCOMPLETE") from None
        except ProjectAuthorizationError as error: raise SurveyAssignmentReviewError(error.code) from None
        except RuntimeLicenseError: raise SurveyAssignmentReviewError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error: raise SurveyAssignmentReviewError(error.code) from None
        except (ValueError, LookupError) as error:
            code = str(error)
            if code in ("CONFLICT_VERSION", "SURVEY_ASSIGNMENT_STATE_INVALID", "RESOURCE_NOT_FOUND"): raise SurveyAssignmentReviewError(code) from None
            raise SurveyAssignmentReviewError() from None
        except Exception: raise SurveyAssignmentReviewError() from None

    def _evidence_names(self, tx, command, snapshot):
        names = {}
        for answer in snapshot.answers:
            for expected in answer.evidence:
                proof = self._evidence.prove(tx, EvidenceFixedProjectQuery(command.session_token, command.trace_id, command.project_id), expected.evidence_id)
                if (type(proof) is not VerifiedProjectEvidence or proof.document_id != expected.document_id
                        or proof.document_version_id != expected.document_version_id
                        or proof.observed_lock_version != expected.observed_lock_version
                        or not hmac.compare_digest(proof.content_fingerprint, expected.content_fingerprint)
                        or proof.document_category == "TEMPLATE"):
                    raise SurveyAssignmentReviewError("SURVEY_ASSIGNMENT_INCOMPLETE")
                if type(proof.original_display_name) is str: names[expected.evidence_id] = proof.original_display_name
        return names

    @staticmethod
    def _validate(command, target):
        if (type(command) is not ReviewSurveyAssignment or type(command.session_token) is not bytes
                or len(command.session_token) != 32 or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32 or any(type(item) is not uuid.UUID or item.int == 0 for item in
                (command.trace_id, command.project_id, command.survey_round_id, command.survey_assignment_id))
                or type(command.expected_lock_version) is not int or command.expected_lock_version < 0):
            raise SurveyAssignmentReviewError("VALIDATION_FAILED")
        if target == "VALIDATED":
            if command.return_comment is not None: raise SurveyAssignmentReviewError("VALIDATION_FAILED")
            return None
        if type(command.return_comment) is not str: raise SurveyAssignmentReviewError("VALIDATION_FAILED")
        comment = unicodedata.normalize("NFKC", command.return_comment).strip()
        if not 1 <= len(comment) <= 2000 or any(unicodedata.category(c)[0] == "C" for c in comment):
            raise SurveyAssignmentReviewError("VALIDATION_FAILED")
        return comment

    @staticmethod
    def _matches(result, command, target, comment):
        return (type(result) is SurveyAssignmentReviewReceipt and result.survey_assignment_id == command.survey_assignment_id
                and result.survey_round_id == command.survey_round_id and result.project_id == command.project_id
                and result.submission_state == target and result.etag == f'"v{command.expected_lock_version + 1}"'
                and result.return_comment == comment)
