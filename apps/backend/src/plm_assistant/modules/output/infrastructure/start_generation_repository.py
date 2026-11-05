"""Output-owned atomic generation-start update; caller owns the shared UOW."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.start_generation import (
    OutputGenerationStartError, OutputGenerationStartFacts,
)
from plm_assistant.modules.output.infrastructure.orm import OutputRequestRow


class SqlAlchemyOutputGenerationStartRepository:
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationStartFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        row = session.scalar(
            select(OutputRequestRow).where(
                OutputRequestRow.output_request_id == request_id,
                OutputRequestRow.project_id == claim.project_id,
                OutputRequestRow.job_ref == claim.job_id,
                OutputRequestRow.context_snapshot_id == snapshot_id,
            ).with_for_update(of=OutputRequestRow)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise OutputGenerationStartError()
        if row.request_state == "GENERATING" and row.current_execution_ref == execution_id:
            return self._facts(row, execution_id, changed=False)
        if (row.request_state != "QUEUED" or row.current_execution_ref is not None
                or row.completed_at is not None):
            raise OutputGenerationStartError()
        return self._facts(row, execution_id, changed=False)

    def start_generation(self, transaction: object, *, claim: ClaimedJob,
                         execution_id: uuid.UUID,
                         expected_lock_version: int) -> OutputGenerationStartFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        row = session.scalar(
            select(OutputRequestRow).where(
                OutputRequestRow.output_request_id == request_id,
                OutputRequestRow.project_id == claim.project_id,
                OutputRequestRow.job_ref == claim.job_id,
                OutputRequestRow.context_snapshot_id == snapshot_id,
            ).with_for_update(of=OutputRequestRow)
            .execution_options(populate_existing=True)
        )
        if (row is None or row.request_state != "QUEUED"
                or row.current_execution_ref is not None or row.completed_at is not None
                or row.lock_version != expected_lock_version):
            raise OutputGenerationStartError()
        row.request_state = "GENERATING"
        row.current_execution_ref = execution_id
        row.lock_version += 1
        session.flush()
        return self._facts(row, execution_id, changed=True)

    @staticmethod
    def _facts(row: OutputRequestRow, execution_id: uuid.UUID, *,
               changed: bool) -> OutputGenerationStartFacts:
        return OutputGenerationStartFacts(
            row.output_request_id, row.project_id, row.job_ref,
            row.context_snapshot_id, row.requested_by, row.output_type,
            execution_id, row.request_state, row.lock_version, changed,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise OutputGenerationStartError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OutputGenerationStartError()
        return session
