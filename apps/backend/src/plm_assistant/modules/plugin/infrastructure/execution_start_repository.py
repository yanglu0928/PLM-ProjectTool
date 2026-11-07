"""SQLAlchemy persistence for PluginExecution start transitions."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.plugin.application.execution_start import (
    PluginExecutionStartError,
    PluginExecutionStartFacts,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginExecutionRow, PluginExecutionStateEventRow,
)


class SqlAlchemyPluginExecutionStartRepository:
    """Uses only the caller's UoW; callers must prove the current Jobs fence."""

    def lock_execution(
        self, transaction: object, *, claim: ClaimedJob,
    ) -> PluginExecutionStartFacts:
        session = self._session(transaction)
        row = session.scalar(
            select(PluginExecutionRow).where(
                PluginExecutionRow.job_id == claim.job_id,
                PluginExecutionRow.project_id == claim.project_id,
                PluginExecutionRow.attempt_no == claim.attempt_no,
            ).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise PluginExecutionStartError()
        return self._facts(row, changed=False)

    def authorize_owner_writes(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_execution_owner_write','on',true)")
        )

    def start_execution(
        self, transaction: object, *, claim: ClaimedJob,
        plugin_execution_id: uuid.UUID, expected_lock_version: int,
    ) -> PluginExecutionStartFacts:
        session = self._session(transaction)
        row = session.scalar(
            select(PluginExecutionRow).where(
                PluginExecutionRow.plugin_execution_id == plugin_execution_id,
                PluginExecutionRow.project_id == claim.project_id,
                PluginExecutionRow.job_id == claim.job_id,
                PluginExecutionRow.attempt_no == claim.attempt_no,
                PluginExecutionRow.execution_state == "PENDING",
                PluginExecutionRow.lock_version == expected_lock_version,
            ).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise PluginExecutionStartError()
        row.execution_state = "RUNNING"
        row.started_at = func.statement_timestamp()
        row.lock_version += 1
        session.flush()
        return self._facts(row, changed=True)

    def append_state_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, from_state: str, to_state: str,
        trace_id: uuid.UUID,
    ) -> None:
        if from_state != "PENDING" or to_state != "RUNNING":
            raise PluginExecutionStartError()
        session = self._session(transaction)
        session.add(PluginExecutionStateEventRow(
            plugin_execution_id=plugin_execution_id,
            project_id=project_id,
            from_state=from_state,
            to_state=to_state,
            reason_code="WORKER_STARTED",
            actor_id=None,
            trace_id=trace_id,
        ))
        session.flush()

    @staticmethod
    def _facts(row: PluginExecutionRow, *, changed: bool) -> PluginExecutionStartFacts:
        return PluginExecutionStartFacts(
            plugin_execution_id=row.plugin_execution_id,
            project_id=row.project_id,
            job_id=row.job_id,
            attempt_no=row.attempt_no,
            execution_state=row.execution_state,
            lock_version=row.lock_version,
            changed=changed,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginExecutionStartError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginExecutionStartError()
        return session
