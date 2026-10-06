"""Caller-transaction proof that an open Survey Round is complete."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectQuery, VerifiedProjectEvidence
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint

from .submission_completeness import SurveySubmissionIncomplete, evaluate_submission
from .submission_views import SurveyAssignmentSubmissionSnapshot


class SurveyRoundCompletenessError(RuntimeError):
    def __init__(self, code="SURVEY_ROUND_INCOMPLETE"):
        self.code = code; super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyRoundCompletenessQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    actor_id: uuid.UUID
    actor_role: str


@dataclass(frozen=True, slots=True)
class SurveyRoundCompletenessContext:
    survey_round_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    target_department_ids: tuple[uuid.UUID, ...]
    assignments: tuple[tuple[uuid.UUID, uuid.UUID, int], ...]


@dataclass(frozen=True, slots=True)
class SurveyRoundCompletenessProof:
    survey_round_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    assignment_count: int
    target_department_count: int
    active_question_count: int
    answered_question_count: int
    evidence_count: int
    report_fingerprint: bytes = field(repr=False)


class SurveyRoundCompletenessOwner:
    def __init__(self, *, repository, submissions, evidence_owner):
        if any(item is None for item in (repository, submissions, evidence_owner)):
            raise ValueError("Round completeness dependencies required")
        self._repository, self._submissions, self._evidence = repository, submissions, evidence_owner

    def prove(self, transaction, query):
        if (transaction is None or type(query) is not SurveyRoundCompletenessQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    query.trace_id, query.project_id, query.survey_round_id, query.actor_id))
                or query.actor_role not in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
            raise SurveyRoundCompletenessError("RESOURCE_NOT_FOUND")
        try:
            context = self._repository.lock_context(
                transaction, project_id=query.project_id,
                survey_round_id=query.survey_round_id)
            if type(context) is not SurveyRoundCompletenessContext or not context.assignments:
                raise SurveyRoundCompletenessError()
            assigned_departments = {item[1] for item in context.assignments}
            if assigned_departments != set(context.target_department_ids):
                raise SurveyRoundCompletenessError()
            snapshots = []
            active = answered = evidence_count = 0
            for assignment_id, _, lock_version in context.assignments:
                snapshot = self._submissions.lock_snapshot(
                    transaction, project_id=query.project_id,
                    survey_round_id=query.survey_round_id,
                    survey_assignment_id=assignment_id,
                    expected_lock_version=lock_version, actor_id=query.actor_id,
                    actor_role=query.actor_role, required_state="VALIDATED",
                    manager_access=True)
                if type(snapshot) is not SurveyAssignmentSubmissionSnapshot:
                    raise SurveyRoundCompletenessError()
                report = evaluate_submission(
                    snapshot, self._evidence_names(transaction, query, snapshot))
                active += report.active_question_count
                answered += report.answered_question_count
                evidence_count += report.evidence_count
                snapshots.append(snapshot)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(context.project_id),
                "survey_round_id": str(context.survey_round_id),
                "survey_version_id": str(context.survey_version_id),
                "targets": [str(value) for value in context.target_department_ids],
                "assignments": [{
                    "assignment_id": str(snapshot.survey_assignment_id),
                    "lock_version": snapshot.before_lock_version,
                    "responses": [{
                        "response_id": str(answer.survey_response_id),
                        "evidence": [{"id": str(item.evidence_id),
                                      "lock": item.observed_lock_version,
                                      "fingerprint": item.content_fingerprint.hex()}
                                     for item in answer.evidence],
                    } for answer in snapshot.answers],
                } for snapshot in snapshots],
            })
            return SurveyRoundCompletenessProof(
                context.survey_round_id, context.survey_version_id,
                context.project_id, len(snapshots), len(context.target_department_ids),
                active, answered, evidence_count, fingerprint)
        except SurveyRoundCompletenessError: raise
        except SurveySubmissionIncomplete: raise SurveyRoundCompletenessError() from None
        except Exception: raise SurveyRoundCompletenessError() from None

    def _evidence_names(self, transaction, query, snapshot):
        names = {}
        for answer in snapshot.answers:
            for expected in answer.evidence:
                proof = self._evidence.prove(transaction, EvidenceFixedProjectQuery(
                    query.session_token, query.trace_id, query.project_id), expected.evidence_id)
                if (type(proof) is not VerifiedProjectEvidence
                        or proof.document_id != expected.document_id
                        or proof.document_version_id != expected.document_version_id
                        or proof.observed_lock_version != expected.observed_lock_version
                        or not hmac.compare_digest(proof.content_fingerprint, expected.content_fingerprint)
                        or proof.document_category == "TEMPLATE"):
                    raise SurveyRoundCompletenessError()
                if type(proof.original_display_name) is str:
                    names[expected.evidence_id] = proof.original_display_name
        return names
