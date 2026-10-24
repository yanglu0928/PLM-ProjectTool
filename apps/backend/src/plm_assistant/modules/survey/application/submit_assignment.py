"""Authorized Survey Assignment completeness check and SUBMITTED transition."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

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
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)

from .submission_completeness import SurveySubmissionIncomplete, evaluate_submission
from .submission_views import (
    SurveyAssignmentSubmissionSnapshot, SurveyAssignmentSubmitReceipt,
)


_OPERATION = "V1_SURVEY_ASSIGNMENT_SUBMIT"


class SurveyAssignmentSubmitError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ASSIGNMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SubmitSurveyAssignment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_assignment_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


class SurveyAssignmentSubmitService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: object, receipts: object, audit: AuditService,
                 evidence_owner: object,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, authorization, repository,
                receipts, audit, evidence_owner)):
            raise ValueError("Survey Assignment submit dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit, self._evidence = receipts, audit, evidence_owner
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitSurveyAssignment) -> SurveyAssignmentSubmitReceipt:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_round_id": str(command.survey_round_id),
                "survey_assignment_id": str(command.survey_assignment_id),
                "expected_lock_version": command.expected_lock_version,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_ASSIGNMENT_SUBMIT")
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_ASSIGNMENT_SUBMIT"):
                    raise SurveyAssignmentSubmitError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != _OPERATION or replay.status_code != 200
                            or replay.ref_id != command.survey_assignment_id):
                        raise SurveyAssignmentSubmitError()
                    result = self._repository.replay(
                        tx, project_id=command.project_id,
                        survey_round_id=command.survey_round_id,
                        survey_assignment_id=command.survey_assignment_id,
                        actor_id=actor, actor_role=authorized.project_role,
                        result_version=command.expected_lock_version + 1)
                    if not self._matches(result, command):
                        raise SurveyAssignmentSubmitError()
                    return result
                snapshot = self._repository.lock_snapshot(
                    tx, project_id=command.project_id,
                    survey_round_id=command.survey_round_id,
                    survey_assignment_id=command.survey_assignment_id,
                    expected_lock_version=command.expected_lock_version,
                    actor_id=actor, actor_role=authorized.project_role)
                if type(snapshot) is not SurveyAssignmentSubmissionSnapshot:
                    raise SurveyAssignmentSubmitError("RESOURCE_NOT_FOUND")
                names = self._reprove_evidence(tx, command, snapshot)
                evaluate_submission(snapshot, names)
                result = self._repository.submit(
                    tx, snapshot=snapshot, actor_id=actor)
                if not self._matches(result, command):
                    raise SurveyAssignmentSubmitError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_ASSIGNMENT_SUBMITTED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-04",
                    target_object_id=command.survey_assignment_id,
                    target_version_id=snapshot.survey_version_id,
                    before_state="IN_PROGRESS", after_state="SUBMITTED"))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyAssignmentSubmitError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, command.survey_assignment_id, 200))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except SurveyAssignmentSubmitError:
            raise
        except SurveySubmissionIncomplete:
            raise SurveyAssignmentSubmitError("SURVEY_ASSIGNMENT_INCOMPLETE") from None
        except ProjectAuthorizationError as error:
            raise SurveyAssignmentSubmitError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyAssignmentSubmitError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyAssignmentSubmitError(error.code) from None
        except EvidenceFixedSourceError as error:
            if error.code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED"):
                raise SurveyAssignmentSubmitError(error.code) from None
            raise SurveyAssignmentSubmitError("SURVEY_ASSIGNMENT_INCOMPLETE") from None
        except LookupError as error:
            raise SurveyAssignmentSubmitError(str(error)) from None
        except ValueError as error:
            code = str(error)
            if code in ("CONFLICT_VERSION", "SURVEY_ASSIGNMENT_STATE_INVALID"):
                raise SurveyAssignmentSubmitError(code) from None
            raise SurveyAssignmentSubmitError() from None
        except Exception:
            raise SurveyAssignmentSubmitError() from None

    def _reprove_evidence(self, tx, command, snapshot):
        names: dict[uuid.UUID, str] = {}
        observed = {}
        for answer in snapshot.answers:
            for item in answer.evidence:
                prior = observed.setdefault(item.evidence_id, item)
                if prior != item:
                    raise SurveyAssignmentSubmitError("SURVEY_ASSIGNMENT_INCOMPLETE")
        for evidence_id, expected in observed.items():
            proof = self._evidence.prove(
                tx, EvidenceFixedProjectQuery(
                    command.session_token, command.trace_id, command.project_id),
                evidence_id)
            if (type(proof) is not VerifiedProjectEvidence
                    or proof.project_id != command.project_id
                    or proof.evidence_id != evidence_id
                    or proof.document_id != expected.document_id
                    or proof.document_version_id != expected.document_version_id
                    or proof.observed_lock_version != expected.observed_lock_version
                    or not hmac.compare_digest(
                        proof.content_fingerprint, expected.content_fingerprint)
                    or proof.document_category == "TEMPLATE"):
                raise SurveyAssignmentSubmitError("SURVEY_ASSIGNMENT_INCOMPLETE")
            if type(proof.original_display_name) is str:
                names[evidence_id] = proof.original_display_name
        return names

    def _actor(self, tx, command):
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=self._now())
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyAssignmentSubmitError("AUTH_ACCESS_DENIED")
        return actor

    def _now(self):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyAssignmentSubmitError()
        return now.astimezone(timezone.utc)

    @staticmethod
    def _validate(command):
        if (type(command) is not SubmitSurveyAssignment
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                    command.trace_id, command.project_id, command.survey_round_id,
                    command.survey_assignment_id))
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 2**63 - 1):
            raise SurveyAssignmentSubmitError("VALIDATION_FAILED")

    @staticmethod
    def _matches(result, command):
        return (type(result) is SurveyAssignmentSubmitReceipt
                and result.survey_assignment_id == command.survey_assignment_id
                and result.survey_round_id == command.survey_round_id
                and result.project_id == command.project_id
                and result.submission_state == "SUBMITTED"
                and result.etag == f'"v{command.expected_lock_version + 1}"')
