from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.fail_generation import FAILURE_CODES
from plm_assistant.modules.plugin.application.execution_failure import (
    PluginExecutionFailureError, PluginExecutionFailureFacts,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginExecutionRow, PluginExecutionStateEventRow,
)


class SqlAlchemyPluginExecutionFailureRepository:
    """Persist only the caller's transaction; caller proves the active Job lease."""

    def lock_running(
        self, transaction: object, *, claim: ClaimedJob,
    ) -> PluginExecutionFailureFacts:
        session = self._session(transaction)
        request_id, context_id = self._payload_ids(claim)
        row = session.scalar(
            select(PluginExecutionRow).where(
                PluginExecutionRow.project_id == claim.project_id,
                PluginExecutionRow.job_id == claim.job_id,
                PluginExecutionRow.output_request_id == request_id,
                PluginExecutionRow.output_context_snapshot_id == context_id,
                PluginExecutionRow.attempt_no == claim.attempt_no,
                PluginExecutionRow.execution_state == "RUNNING",
            ).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise PluginExecutionFailureError()
        return self._facts(row, changed=False)

    def authorize_owner_writes(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_execution_owner_write','on',true)")
        )

    def fail_execution(
        self, transaction: object, *, claim: ClaimedJob,
        plugin_execution_id: uuid.UUID, expected_lock_version: int,
        error_code: str,
    ) -> PluginExecutionFailureFacts:
        if type(error_code) is not str or error_code not in FAILURE_CODES:
            raise PluginExecutionFailureError()
        session = self._session(transaction)
        request_id, context_id = self._payload_ids(claim)
        row = session.scalar(
            select(PluginExecutionRow).where(
                PluginExecutionRow.plugin_execution_id == plugin_execution_id,
                PluginExecutionRow.project_id == claim.project_id,
                PluginExecutionRow.job_id == claim.job_id,
                PluginExecutionRow.output_request_id == request_id,
                PluginExecutionRow.output_context_snapshot_id == context_id,
                PluginExecutionRow.attempt_no == claim.attempt_no,
                PluginExecutionRow.execution_state == "RUNNING",
                PluginExecutionRow.lock_version == expected_lock_version,
            ).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise PluginExecutionFailureError()
        row.execution_state = "FAILED"
        row.completed_at = func.statement_timestamp()
        row.error_code = error_code
        row.retryable = False
        row.lock_version += 1
        session.flush()
        return self._facts(row, changed=True)

    def append_failed_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, trace_id: uuid.UUID, error_code: str,
    ) -> None:
        if type(error_code) is not str or error_code not in FAILURE_CODES:
            raise PluginExecutionFailureError()
        session = self._session(transaction)
        session.add(PluginExecutionStateEventRow(
            plugin_execution_id=plugin_execution_id,
            project_id=project_id, from_state="RUNNING", to_state="FAILED",
            reason_code=error_code, actor_id=None, trace_id=trace_id,
        ))
        session.flush()

    @staticmethod
    def _facts(row: PluginExecutionRow, *, changed: bool) -> PluginExecutionFailureFacts:
        return PluginExecutionFailureFacts(
            plugin_execution_id=row.plugin_execution_id,
            project_id=row.project_id, job_id=row.job_id,
            output_request_id=row.output_request_id,
            output_context_snapshot_id=row.output_context_snapshot_id,
            attempt_no=row.attempt_no, trace_id=row.trace_id,
            execution_state=row.execution_state, lock_version=row.lock_version,
            changed=changed,
        )

    @staticmethod
    def _payload_ids(claim: ClaimedJob) -> tuple[uuid.UUID, uuid.UUID]:
        values = claim.payload_refs
        if type(values) is not dict or set(values) != {
            "output_request_id", "context_snapshot_id",
        }:
            raise PluginExecutionFailureError()
        try:
            request_id = uuid.UUID(values["output_request_id"])
            context_id = uuid.UUID(values["context_snapshot_id"])
        except (TypeError, ValueError, AttributeError):
            raise PluginExecutionFailureError() from None
        if (str(request_id) != values["output_request_id"]
                or str(context_id) != values["context_snapshot_id"]
                or not request_id.int or not context_id.int):
            raise PluginExecutionFailureError()
        return request_id, context_id

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginExecutionFailureError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginExecutionFailureError()
        return session
