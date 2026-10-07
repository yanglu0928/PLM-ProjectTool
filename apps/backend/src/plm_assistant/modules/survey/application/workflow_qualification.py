"""Survey-owned current-fact qualification for Workflow stage checks."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError,
    ChecklistQualificationEvidence,
    ChecklistQualificationReview,
    CurrentChecklistQualification,
    CurrentChecklistQualificationQuery,
)

from .conclusion_sources import (
    ConclusionResponseEvidenceProof, ConclusionResponseProof,
)
from .validate_conclusion import (
    ConclusionValidationSnapshot, SurveyConclusionCurrentValidator,
    ValidateSurveyConclusion,
)


_ITEMS = frozenset({"SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"})


class SurveyWorkflowQualificationError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SURVEY_WORKFLOW_NOT_QUALIFIED")


@dataclass(frozen=True, slots=True)
class SurveyWorkflowQualificationLock:
    snapshot: ConclusionValidationSnapshot
    survey_state: str
    review_id: uuid.UUID
    review_round_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not ConclusionValidationSnapshot
                or self.survey_state != "ACTIVE"
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (self.review_id, self.review_round_id))
                or self.snapshot.conclusion_state != "APPROVED"):
            raise SurveyWorkflowQualificationError()


class SurveyWorkflowQualificationRepositoryPort(Protocol):
    def lock_only_current_approved(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> SurveyWorkflowQualificationLock | None: ...


class SurveyWorkflowResponsePort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, round_refs: tuple[uuid.UUID, ...],
        response_id: uuid.UUID,
    ) -> ConclusionResponseProof | None: ...


class SurveyWorkflowEvidencePort(Protocol):
    def prove(
        self, transaction: object, query: EvidenceFixedProjectQuery,
        evidence_id: uuid.UUID,
    ) -> VerifiedProjectEvidence: ...


class SurveyWorkflowReviewPort(Protocol):
    def get_round(
        self, transaction: object, scope: str,
        project_id: uuid.UUID | None, review_id: uuid.UUID,
        round_id: uuid.UUID,
    ) -> FixedReviewRoundSnapshot | None: ...


class SurveyWorkflowQualificationPolicy:
    def qualify(
        self, *, item_key: str, lock: SurveyWorkflowQualificationLock,
        evidence: tuple[ChecklistQualificationEvidence, ...],
        review: ChecklistQualificationReview,
        response_ids: tuple[uuid.UUID, ...],
        project_record_ids: tuple[uuid.UUID, ...],
    ) -> CurrentChecklistQualification:
        if (item_key not in _ITEMS
                or type(lock) is not SurveyWorkflowQualificationLock
                or type(evidence) is not tuple or not evidence
                or type(review) is not ChecklistQualificationReview
                or type(response_ids) is not tuple
                or type(project_record_ids) is not tuple
                or not response_ids and not project_record_ids):
            raise SurveyWorkflowQualificationError()
        lock.__post_init__()
        snapshot = lock.snapshot
        payload = {
            "schema": "survey-workflow-qualification.v1",
            "item_key": item_key,
            "project_id": str(snapshot.project_id),
            "survey_id": str(snapshot.survey_id),
            "conclusion_series_id": str(snapshot.conclusion_series_id),
            "survey_conclusion_id": str(snapshot.survey_conclusion_id),
            "conclusion_fingerprint": snapshot.content_fingerprint.hex(),
            "response_ids": [str(value) for value in response_ids],
            "project_record_ids": [str(value) for value in project_record_ids],
            "review_round_id": str(review.review_round_id),
            "evidence": [{
                "evidence_id": str(value.evidence_id),
                "lock_version": value.observed_lock_version,
                "content_fingerprint": value.content_fingerprint.hex(),
            } for value in evidence],
        }
        return CurrentChecklistQualification(
            snapshot.project_id, "SURVEY", item_key, "SRV-05",
            snapshot.conclusion_series_id, snapshot.survey_conclusion_id,
            canonical_payload_fingerprint(payload), evidence, review,
        )


class SurveyWorkflowQualificationOwner:
    def __init__(
        self, *, repository: SurveyWorkflowQualificationRepositoryPort,
        current: SurveyConclusionCurrentValidator,
        responses: SurveyWorkflowResponsePort,
        evidence: SurveyWorkflowEvidencePort,
        reviews: SurveyWorkflowReviewPort,
        policy: SurveyWorkflowQualificationPolicy | None = None,
        clock=None,
    ) -> None:
        if any(value is None for value in (
                repository, current, responses, evidence, reviews)):
            raise ValueError("Survey Workflow qualification dependencies required")
        self._repo, self._current, self._responses = (
            repository, current, responses,
        )
        self._evidence, self._reviews = evidence, reviews
        self._policy = policy or SurveyWorkflowQualificationPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification:
        if (transaction is None
                or type(query) is not CurrentChecklistQualificationQuery
                or query.item_key not in _ITEMS):
            raise ChecklistQualificationError()
        query.__post_init__()
        try:
            lock = self._repo.lock_only_current_approved(
                transaction, project_id=query.project_id,
            )
            if type(lock) is not SurveyWorkflowQualificationLock:
                raise SurveyWorkflowQualificationError()
            lock.__post_init__()
            snapshot = lock.snapshot
            if snapshot.project_id != query.project_id:
                raise SurveyWorkflowQualificationError()
            facts = self._current.current_facts(
                transaction,
                ValidateSurveyConclusion(
                    query.session_token, b"x" * 32, query.trace_id,
                    query.project_id, snapshot.survey_conclusion_id,
                    "x" * 16,
                ),
                snapshot,
            )
            if type(facts.issues) is not tuple or facts.issues:
                raise SurveyWorkflowQualificationError()
            now = self._now()
            response_ids, constraints = self._response_constraints(
                transaction, snapshot,
            )
            project_records = tuple(
                value.evidence_id for value, role in zip(
                    snapshot.evidence, snapshot.evidence_roles, strict=False,
                ) if role == "SUPPORT"
            )
            for value in snapshot.evidence:
                constraints.setdefault(value.evidence_id, []).append((
                    value.document_id, value.document_version_id,
                    value.observed_evidence_lock_version,
                    value.content_fingerprint,
                ))
            observations = self._prove_evidence(
                transaction, query, constraints, now,
            )
            review = self._prove_review(
                transaction, lock, now,
            )
            result = self._policy.qualify(
                item_key=query.item_key, lock=lock,
                evidence=observations, review=review,
                response_ids=response_ids,
                project_record_ids=project_records,
            )
            result.__post_init__()
            return result
        except ChecklistQualificationError:
            raise
        except Exception:
            raise ChecklistQualificationError() from None

    def _response_constraints(self, tx, snapshot):
        response_ids = tuple(sorted({
            response_id
            for item in (*snapshot.departments, *snapshot.modules)
            for response_id in item.response_refs
        }, key=lambda value: value.int))
        constraints: dict[uuid.UUID, list[tuple[object, ...]]] = {}
        for response_id in response_ids:
            proof = self._responses.prove(
                tx, project_id=snapshot.project_id,
                survey_id=snapshot.survey_id,
                round_refs=snapshot.round_refs,
                response_id=response_id,
            )
            if (type(proof) is not ConclusionResponseProof
                    or proof.response_id != response_id
                    or proof.project_id != snapshot.project_id
                    or proof.survey_id != snapshot.survey_id
                    or proof.round_id not in snapshot.round_refs
                    or type(proof.evidence) is not tuple
                    or proof.evidence_ids
                       != tuple(value.evidence_id for value in proof.evidence)):
                raise SurveyWorkflowQualificationError()
            for value in proof.evidence:
                if type(value) is not ConclusionResponseEvidenceProof:
                    raise SurveyWorkflowQualificationError()
                constraints.setdefault(value.evidence_id, []).append((
                    value.document_id, value.document_version_id,
                    value.observed_evidence_lock_version,
                    value.content_fingerprint,
                ))
        return response_ids, constraints

    def _prove_evidence(self, tx, query, constraints, now):
        if not constraints:
            raise SurveyWorkflowQualificationError()
        observations = []
        evidence_query = EvidenceFixedProjectQuery(
            query.session_token, query.trace_id, query.project_id,
        )
        for evidence_id in sorted(constraints, key=lambda value: value.int):
            proof = self._evidence.prove(tx, evidence_query, evidence_id)
            if (type(proof) is not VerifiedProjectEvidence
                    or proof.evidence_id != evidence_id
                    or proof.project_id != query.project_id
                    or proof.scope != "PROJECT"
                    or proof.observed_state != "ELIGIBLE"
                    or proof.document_category == "TEMPLATE"):
                raise SurveyWorkflowQualificationError()
            for document_id, version_id, lock_version, fingerprint in constraints[evidence_id]:
                if (proof.document_id != document_id
                        or proof.document_version_id != version_id
                        or proof.observed_lock_version != lock_version
                        or type(fingerprint) is not bytes
                        or not hmac.compare_digest(
                            proof.content_fingerprint, fingerprint,
                        )):
                    raise SurveyWorkflowQualificationError()
            observations.append(ChecklistQualificationEvidence(
                proof.evidence_id, proof.project_id,
                proof.observed_lock_version, proof.content_fingerprint, now,
            ))
        return tuple(observations)

    def _prove_review(self, tx, lock, now):
        snapshot = lock.snapshot
        fixed = self._reviews.get_round(
            tx, "PROJECT", snapshot.project_id,
            lock.review_id, lock.review_round_id,
        )
        if type(fixed) is not FixedReviewRoundSnapshot:
            raise SurveyWorkflowQualificationError()
        fixed.__post_init__()
        identity = fixed.review
        if (identity.review_id != lock.review_id
                or identity.scope != "PROJECT"
                or identity.project_id != snapshot.project_id
                or identity.subject_type != "SRV-05"
                or identity.subject_id != snapshot.conclusion_series_id
                or identity.policy_code != "SURVEY_CONCLUSION_ALL_V1"
                or identity.state != "APPROVED"
                or fixed.progress.round_id != lock.review_round_id
                or fixed.progress.state is not ReviewRoundState.APPROVED
                or fixed.subject_version_id != snapshot.survey_conclusion_id
                or not hmac.compare_digest(
                    fixed.subject_fingerprint, snapshot.content_fingerprint,
                )):
            raise SurveyWorkflowQualificationError()
        return ChecklistQualificationReview(
            identity.review_id, fixed.progress.round_id,
            snapshot.project_id, snapshot.conclusion_series_id,
            snapshot.survey_conclusion_id, fixed.round_lock_version,
            fixed.subject_fingerprint, now, identity.subject_type,
            identity.policy_code,
        )

    def _now(self):
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise SurveyWorkflowQualificationError()
        return now.astimezone(timezone.utc)
