"""SQLAlchemy Output repository for retry or exhausted failure transition."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError, OutputGenerationFailureFacts,
)
from plm_assistant.modules.output.application.retry_generation import (
    OutputGenerationRetryError,
)
from plm_assistant.modules.output.infrastructure.orm import OutputRequestRow


class SqlAlchemyOutputGenerationRetryRepository:
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationFailureFacts:
        session = self._session(transaction)
        row = self._locked_row(session, claim)
        if row is None or row.request_state != "GENERATING" or row.current_execution_ref != execution_id:
            raise OutputGenerationRetryError()
        return self._facts(row, execution_id, changed=False)

    def transition_retry(self, transaction: object, *, claim: ClaimedJob,
                         execution_id: uuid.UUID, expected_lock_version: int,
                         target_state: str) -> OutputGenerationFailureFacts:
        session = self._session(transaction)
        row = self._locked_row(session, claim)
        if (row is None or row.request_state != "GENERATING"
                or row.current_execution_ref != execution_id or row.completed_at is not None
                or row.lock_version != expected_lock_version
                or target_state not in {"QUEUED", "FAILED"}):
            raise OutputGenerationRetryError()
        row.request_state = target_state
        row.lock_version += 1
        if target_state == "QUEUED":
            row.current_execution_ref = None
        else:
            row.completed_at = session.scalar(select(func.statement_timestamp()))
        session.flush()
        return self._facts(row, execution_id, changed=True)

    @staticmethod
    def _locked_row(session: Session, claim: ClaimedJob):
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        return session.scalar(
            select(OutputRequestRow).where(
                OutputRequestRow.output_request_id == request_id,
                OutputRequestRow.project_id == claim.project_id,
                OutputRequestRow.job_ref == claim.job_id,
                OutputRequestRow.context_snapshot_id == snapshot_id,
            ).with_for_update(of=OutputRequestRow)
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def _facts(row: OutputRequestRow, execution_id: uuid.UUID, *,
               changed: bool) -> OutputGenerationFailureFacts:
        return OutputGenerationFailureFacts(
            row.output_request_id, row.project_id, row.job_ref,
            row.context_snapshot_id, row.requested_by, execution_id,
            row.request_state, row.lock_version, changed,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise OutputGenerationRetryError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OutputGenerationRetryError()
        return session
