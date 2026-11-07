"""Project-scoped OutputRequest fixed-version projection."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from plm_assistant.modules.output.application.read_request import (
    OutputRequestReadError, OutputRequestView,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow, OutputRequestRow,
)


class SqlAlchemyOutputRequestReadRepository:
    def get(self, transaction: object, *, project_id: uuid.UUID,
            output_request_id: uuid.UUID) -> OutputRequestView | None:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise RuntimeError("active Output transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Output transaction is required")
        row = session.execute(
            select(
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
            ).where(
                OutputRequestRow.project_id == project_id,
                OutputRequestRow.output_request_id == output_request_id,
            )
        ).one_or_none()
        if row is None:
            return None
        try:
            source_values = row.source_version_refs
            if type(source_values) is not list or not source_values:
                raise ValueError("invalid stored source refs")
            source_refs = tuple(uuid.UUID(value) for value in source_values)
            if (len(set(source_refs)) != len(source_refs)
                    or any(not value.int for value in source_refs)
                    or type(row.context_fingerprint) is not bytes
                    or len(row.context_fingerprint) != 32
                    or type(row.request_state) is not str
                    or row.request_state not in {
                        "REQUESTED", "QUEUED", "GENERATING", "VALIDATING",
                        "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
                    }
                    or type(row.output_type) is not str
                    or row.output_type not in {"DOCX", "PPTX", "PNG", "JPEG"}
                    or type(row.generation_no) is not int or row.generation_no < 1
                    or type(row.lock_version) is not int or row.lock_version < 0
                    or row.requested_at.tzinfo is None
                    or (row.completed_at is not None and row.completed_at.tzinfo is None)
                    or (row.job_ref is not None and type(row.job_ref) is not uuid.UUID)
                    or (row.current_execution_ref is not None
                        and type(row.current_execution_ref) is not uuid.UUID)):
                raise ValueError("invalid stored OutputRequest projection")
            return OutputRequestView(
                output_request_id=row.output_request_id,
                project_id=row.project_id,
                output_type=row.output_type,
                template_version_ref=row.template_version_ref,
                source_version_refs=source_refs,
                output_policy_ref=row.output_policy_ref,
                plugin_operation=row.plugin_operation,
                context_snapshot_ref=row.context_snapshot_id,
                context_fingerprint=row.context_fingerprint,
                request_state=row.request_state,
                job_ref=row.job_ref,
                execution_ref=row.current_execution_ref,
                generation_no=row.generation_no,
                requested_at=row.requested_at,
                completed_at=row.completed_at,
                lock_version=row.lock_version,
            )
        except (AttributeError, TypeError, ValueError):
            raise OutputRequestReadError("SYSTEM_UNAVAILABLE") from None
