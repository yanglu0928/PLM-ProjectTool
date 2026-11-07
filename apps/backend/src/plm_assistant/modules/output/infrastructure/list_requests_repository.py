"""Project-scoped, stable-keyset OutputRequest history reads."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from plm_assistant.modules.output.application.list_requests import (
    OutputRequestListError,
)
from plm_assistant.modules.output.application.read_request import OutputRequestView
from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow, OutputRequestRow,
)


class SqlAlchemyOutputRequestListRepository:
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_requested_at: datetime | None,
                  after_request_id: uuid.UUID | None,
                  limit: int) -> tuple[OutputRequestView, ...]:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise RuntimeError("active Output transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Output transaction is required")
        statement = select(
            OutputRequestRow.output_request_id,
            OutputRequestRow.project_id,
            OutputRequestRow.output_type,
            OutputRequestRow.template_version_ref,
            OutputRequestRow.source_version_refs,
            OutputRequestRow.output_policy_ref,
            OutputRequestRow.plugin_operation,
            OutputRequestRow.context_snapshot_id,
            OutputContextSnapshotRow.context_fingerprint,
            OutputRequestRow.request_state,
            OutputRequestRow.job_ref,
            OutputRequestRow.current_execution_ref,
            OutputRequestRow.generation_no,
            OutputRequestRow.requested_at,
            OutputRequestRow.completed_at,
            OutputRequestRow.lock_version,
        ).join(
            OutputContextSnapshotRow,
            and_(
                OutputContextSnapshotRow.context_snapshot_id
                == OutputRequestRow.context_snapshot_id,
                OutputContextSnapshotRow.project_id == OutputRequestRow.project_id,
            ),
        ).where(OutputRequestRow.project_id == project_id)
        if (after_requested_at is None) != (after_request_id is None):
            raise OutputRequestListError("VALIDATION_FAILED")
        if after_requested_at is not None and after_request_id is not None:
            statement = statement.where(or_(
                OutputRequestRow.requested_at < after_requested_at,
                and_(
                    OutputRequestRow.requested_at == after_requested_at,
                    OutputRequestRow.output_request_id < after_request_id,
                ),
            ))
        rows = session.execute(
            statement.order_by(
                OutputRequestRow.requested_at.desc(),
                OutputRequestRow.output_request_id.desc(),
            ).limit(limit)
        ).all()
        return tuple(self._view(row) for row in rows)

    @staticmethod
    def _view(row: object) -> OutputRequestView:
        try:
            source_values = row.source_version_refs
            if type(source_values) is not list or not source_values:
                raise ValueError("invalid source refs")
            source_refs = tuple(uuid.UUID(value) for value in source_values)
            if (len(set(source_refs)) != len(source_refs)
                    or any(not value.int for value in source_refs)
                    or type(row.context_fingerprint) is not bytes
                    or len(row.context_fingerprint) != 32
                    or row.request_state not in {
                        "REQUESTED", "QUEUED", "GENERATING", "VALIDATING",
                        "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
                    }
                    or row.output_type not in {"DOCX", "PPTX", "PNG", "JPEG"}
                    or type(row.generation_no) is not int or row.generation_no < 1
                    or type(row.lock_version) is not int or row.lock_version < 0
                    or row.requested_at.tzinfo is None
                    or (row.completed_at is not None and row.completed_at.tzinfo is None)):
                raise ValueError("invalid stored OutputRequest projection")
            return OutputRequestView(
                output_request_id=row.output_request_id, project_id=row.project_id,
                output_type=row.output_type, template_version_ref=row.template_version_ref,
                source_version_refs=source_refs, output_policy_ref=row.output_policy_ref,
                plugin_operation=row.plugin_operation,
                context_snapshot_ref=row.context_snapshot_id,
                context_fingerprint=row.context_fingerprint,
                request_state=row.request_state, job_ref=row.job_ref,
                execution_ref=row.current_execution_ref,
                generation_no=row.generation_no, requested_at=row.requested_at,
                completed_at=row.completed_at, lock_version=row.lock_version,
            )
        except (AttributeError, TypeError, ValueError):
            raise OutputRequestListError("SYSTEM_UNAVAILABLE") from None
