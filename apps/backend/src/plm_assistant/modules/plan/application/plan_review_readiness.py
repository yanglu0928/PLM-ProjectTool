"""Current, same-transaction proof that a fixed PlanVersion may enter Review."""

from __future__ import annotations

import uuid
import hmac
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.plan.application.read_plan_version import PlanVersionSnapshotView
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionValidationReport,
)


class PlanReviewReadinessDenied(RuntimeError):
    """The fixed PlanVersion is not currently eligible for Review."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def snapshot_fingerprint(snapshot: PlanVersionSnapshotView) -> bytes:
    if type(snapshot) is not PlanVersionSnapshotView or type(snapshot.snapshot) is not dict:
        raise PlanReviewReadinessDenied()
    try:
        encoded = json.dumps(
            snapshot.snapshot, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 8_000_000:
            raise ValueError()
        return hashlib.sha256(encoded).digest()
    except Exception:
        raise PlanReviewReadinessDenied() from None


@dataclass(frozen=True, slots=True)
class PlanVersionReviewLock:
    snapshot: PlanVersionSnapshotView
    latest_version_id: uuid.UUID


class PlanVersionReviewRepositoryPort(Protocol):
    def lock_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID,
                     plan_version_id: uuid.UUID) -> PlanVersionReviewLock | None: ...


class PlanVersionCurrentEvaluatorPort(Protocol):
    def evaluate_snapshot_in_transaction(
        self, transaction: object, *, snapshot: PlanVersionSnapshotView,
        session_token: bytes, trace_id: uuid.UUID,
    ) -> tuple[bytes, PlanVersionValidationReport]: ...


@dataclass(frozen=True, slots=True)
class PlanVersionReviewReadinessQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanVersionReviewTerminalQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    subject_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PlanVersionReviewReadinessProof:
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)
    checked_at: datetime


class PlanVersionReviewReadinessService:
    """Read-only proof; caller owns auth, transaction and Plan identity lock."""

    def __init__(self, *, repository: PlanVersionReviewRepositoryPort,
                 evaluator: PlanVersionCurrentEvaluatorPort) -> None:
        if repository is None or evaluator is None:
            raise ValueError("PlanVersion Review readiness dependencies required")
        self._repository, self._evaluator = repository, evaluator

    def prove_in_transaction(
            self, transaction: object, *,
            query: PlanVersionReviewReadinessQuery,
            ) -> PlanVersionReviewReadinessProof:
        if (type(query) is not PlanVersionReviewReadinessQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not all(_id(value) for value in (
                    query.trace_id, query.project_id, query.plan_id,
                    query.plan_version_id))):
            raise PlanReviewReadinessDenied()
        try:
            locked = self._repository.lock_current(
                transaction, project_id=query.project_id,
                plan_id=query.plan_id, plan_version_id=query.plan_version_id)
            if (type(locked) is not PlanVersionReviewLock
                    or locked.latest_version_id != query.plan_version_id
                    or type(locked.snapshot) is not PlanVersionSnapshotView
                    or locked.snapshot.project_id != query.project_id
                    or locked.snapshot.plan_id != query.plan_id
                    or locked.snapshot.plan_version_id != query.plan_version_id
                    or locked.snapshot.version_state != "DRAFT"
                    or locked.snapshot.review_ref is not None
                    or locked.snapshot.review_round_ref is not None):
                raise PlanReviewReadinessDenied()
            fingerprint, report = self._evaluator.evaluate_snapshot_in_transaction(
                transaction, snapshot=locked.snapshot,
                session_token=query.session_token, trace_id=query.trace_id)
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or type(report) is not PlanVersionValidationReport
                    or report.valid is not True):
                raise PlanReviewReadinessDenied()
            return PlanVersionReviewReadinessProof(
                project_id=query.project_id, plan_id=query.plan_id,
                plan_version_id=query.plan_version_id,
                version_no=locked.snapshot.version_no,
                content_fingerprint=fingerprint, checked_at=report.checked_at)
        except PlanReviewReadinessDenied:
            raise
        except Exception:
            raise PlanReviewReadinessDenied() from None

    def prove_terminal_in_transaction(
            self, transaction: object, *,
            query: PlanVersionReviewTerminalQuery,
            ) -> PlanVersionReviewReadinessProof:
        """Re-prove the exact in-review snapshot and its current sources."""
        if (type(query) is not PlanVersionReviewTerminalQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.subject_fingerprint) is not bytes
                or len(query.subject_fingerprint) != 32
                or not all(_id(value) for value in (
                    query.trace_id, query.project_id, query.plan_id,
                    query.plan_version_id, query.review_id,
                    query.review_round_id))):
            raise PlanReviewReadinessDenied()
        try:
            locked = self._repository.lock_current(
                transaction, project_id=query.project_id,
                plan_id=query.plan_id, plan_version_id=query.plan_version_id)
            if (type(locked) is not PlanVersionReviewLock
                    or locked.latest_version_id != query.plan_version_id
                    or type(locked.snapshot) is not PlanVersionSnapshotView
                    or locked.snapshot.project_id != query.project_id
                    or locked.snapshot.plan_id != query.plan_id
                    or locked.snapshot.plan_version_id != query.plan_version_id
                    or locked.snapshot.version_state != "IN_REVIEW"
                    or locked.snapshot.review_ref != query.review_id
                    or locked.snapshot.review_round_ref != query.review_round_id):
                raise PlanReviewReadinessDenied()
            fingerprint, report = self._evaluator.evaluate_snapshot_in_transaction(
                transaction, snapshot=locked.snapshot,
                session_token=query.session_token, trace_id=query.trace_id)
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or not hmac.compare_digest(fingerprint, query.subject_fingerprint)
                    or type(report) is not PlanVersionValidationReport
                    or report.valid is not True):
                raise PlanReviewReadinessDenied()
            return PlanVersionReviewReadinessProof(
                project_id=query.project_id, plan_id=query.plan_id,
                plan_version_id=query.plan_version_id,
                version_no=locked.snapshot.version_no,
                content_fingerprint=fingerprint, checked_at=report.checked_at)
        except PlanReviewReadinessDenied:
            raise
        except Exception:
            raise PlanReviewReadinessDenied() from None
