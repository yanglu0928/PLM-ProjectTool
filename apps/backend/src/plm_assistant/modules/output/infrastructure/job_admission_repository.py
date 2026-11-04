"""Output-owned read adapter for execution admission facts."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from plm_assistant.modules.output.application.job_admission import (
    OutputJobAdmissionFacts,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow,
    OutputRequestRow,
)


class SqlAlchemyOutputJobAdmissionRepository:
    """Reads only Output-owned rows; caller owns the active transaction."""

    def load(self, transaction: object, *, project_id: uuid.UUID,
             output_request_id: uuid.UUID, job_id: uuid.UUID,
             context_snapshot_id: uuid.UUID) -> OutputJobAdmissionFacts | None:
        session = self._session(transaction)
        row = session.execute(
            select(OutputRequestRow, OutputContextSnapshotRow)
            .join(
                OutputContextSnapshotRow,
                and_(
                    OutputContextSnapshotRow.context_snapshot_id
                    == OutputRequestRow.context_snapshot_id,
                    OutputContextSnapshotRow.project_id
                    == OutputRequestRow.project_id,
                ),
            )
            .where(
                OutputRequestRow.project_id == project_id,
                OutputRequestRow.output_request_id == output_request_id,
                OutputRequestRow.job_ref == job_id,
                OutputRequestRow.context_snapshot_id == context_snapshot_id,
                OutputContextSnapshotRow.context_snapshot_id == context_snapshot_id,
            )
        ).one_or_none()
        if row is None:
            return None
        request, snapshot = row
        try:
            source_values = request.source_version_refs
            snapshot_sources = snapshot.source_version_refs
            if (type(source_values) is not list or not source_values
                    or type(snapshot_sources) is not list):
                return None
            sources = tuple(uuid.UUID(value) for value in source_values)
            if [str(value) for value in sources] != snapshot_sources:
                return None
            if (type(snapshot.context_payload) is not dict
                    or type(snapshot.context_fingerprint) is not bytes):
                return None
            return OutputJobAdmissionFacts(
                output_request_id=request.output_request_id,
                project_id=request.project_id,
                job_id=request.job_ref,
                context_snapshot_id=request.context_snapshot_id,
                request_state=request.request_state,
                output_type=request.output_type,
                template_version_ref=request.template_version_ref,
                source_version_refs=sources,
                output_policy_ref=request.output_policy_ref,
                plugin_operation=request.plugin_operation,
                input_fingerprint=bytes(request.input_fingerprint),
                context_payload=dict(snapshot.context_payload),
                context_fingerprint=bytes(snapshot.context_fingerprint),
            )
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise RuntimeError("OUTPUT_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("OUTPUT_STORE_UNAVAILABLE")
        return session
