"""Immutable Audit-linked persistence for the first PlanVersion Validate report."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionSnapshotView,
)
from plm_assistant.modules.plan.application.validate_plan_version import (
    PlanVersionValidationError,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanVersionValidationResultRow,
)
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import (
    SqlAlchemyPlanVersionReadRepository,
)


class SqlAlchemyPlanVersionValidationRepository:
    def __init__(self, *, snapshots: SqlAlchemyPlanVersionReadRepository | None = None) -> None:
        self._snapshots = snapshots or SqlAlchemyPlanVersionReadRepository()

    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID, plan_version_id: uuid.UUID
                    ) -> PlanVersionSnapshotView | None:
        return self._snapshots.get_current(
            transaction, project_id=project_id, plan_id=plan_id,
            plan_version_id=plan_version_id)

    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID, plan_id: uuid.UUID,
            plan_version_id: uuid.UUID,
            snapshot_fingerprint: bytes) -> PlanVersionValidationReport | None:
        session = _session(transaction)
        try:
            row = session.execute(select(PlanVersionValidationResultRow).join(
                AuditEventRow,
                AuditEventRow.audit_event_id == PlanVersionValidationResultRow.audit_event_id,
            ).where(
                PlanVersionValidationResultRow.audit_event_id == audit_event_id,
                PlanVersionValidationResultRow.project_id == project_id,
                PlanVersionValidationResultRow.plan_id == plan_id,
                PlanVersionValidationResultRow.plan_version_id == plan_version_id,
                PlanVersionValidationResultRow.snapshot_fingerprint == snapshot_fingerprint,
                AuditEventRow.actor_id == actor_id,
                AuditEventRow.event_scope == "PROJECT",
                AuditEventRow.target_project_id == project_id,
                AuditEventRow.action == "PLAN_VERSION_VALIDATED",
                AuditEventRow.outcome == "SUCCESS",
                AuditEventRow.target_owner_module == "plan",
                AuditEventRow.target_object_type == "PLN-02",
                AuditEventRow.target_object_id == plan_version_id,
                AuditEventRow.target_version_id == plan_version_id,
            )).scalar_one_or_none()
        except SQLAlchemyError:
            raise PlanVersionValidationError() from None
        if row is None:
            return None
        try:
            coverage = row.coverage_summary
            if (type(coverage) is not dict
                    or set(coverage) != {
                        "requirement_total", "requirement_mapped",
                        "requirement_excluded", "requirement_uncovered",
                        "solution_total", "solution_mapped",
                        "solution_excluded", "solution_uncovered",
                    }
                    or type(row.blocking_issues) is not list
                    or type(row.warnings) is not list):
                raise ValueError()
            return PlanVersionValidationReport(
                valid=row.valid, blocking_issues=tuple(row.blocking_issues),
                warnings=tuple(row.warnings),
                coverage_summary=PlanVersionCoverageSummary(**coverage),
                checked_at=row.checked_at)
        except (TypeError, ValueError):
            raise PlanVersionValidationError() from None

    def save(self, transaction: object, *, audit_event_id: uuid.UUID,
             snapshot, snapshot_fingerprint: bytes,
             report: PlanVersionValidationReport) -> None:
        if (type(audit_event_id) is not uuid.UUID or audit_event_id.int == 0
                or type(snapshot_fingerprint) is not bytes
                or len(snapshot_fingerprint) != 32
                or type(report) is not PlanVersionValidationReport):
            raise PlanVersionValidationError("VALIDATION_FAILED")
        coverage = report.coverage_summary
        session = _session(transaction)
        try:
            session.add(PlanVersionValidationResultRow(
                audit_event_id=audit_event_id,
                plan_version_id=snapshot.plan_version_id,
                plan_id=snapshot.plan_id, project_id=snapshot.project_id,
                snapshot_fingerprint=snapshot_fingerprint,
                valid=report.valid, blocking_issues=list(report.blocking_issues),
                warnings=list(report.warnings),
                coverage_summary={
                    "requirement_total": coverage.requirement_total,
                    "requirement_mapped": coverage.requirement_mapped,
                    "requirement_excluded": coverage.requirement_excluded,
                    "requirement_uncovered": coverage.requirement_uncovered,
                    "solution_total": coverage.solution_total,
                    "solution_mapped": coverage.solution_mapped,
                    "solution_excluded": coverage.solution_excluded,
                    "solution_uncovered": coverage.solution_uncovered,
                },
                checked_at=report.checked_at,
            ))
            session.flush()
        except SQLAlchemyError:
            raise PlanVersionValidationError() from None
