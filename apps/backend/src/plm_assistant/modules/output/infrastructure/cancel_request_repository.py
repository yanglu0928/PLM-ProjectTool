"""OutputRequest cancellation facts and state update; transaction owned by caller."""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from plm_assistant.modules.output.application.cancel_request import (
    OutputRequestCancelError, OutputRequestCancelFacts,
)
from plm_assistant.modules.output.infrastructure.orm import OutputRequestRow
class SqlAlchemyOutputRequestCancelRepository:
    def get_for_update(self,transaction:object,*,project_id:uuid.UUID,
                       output_request_id:uuid.UUID)->OutputRequestCancelFacts|None:
        row=self._session(transaction).scalar(select(OutputRequestRow).where(
            OutputRequestRow.project_id==project_id,
            OutputRequestRow.output_request_id==output_request_id)
            .with_for_update(of=OutputRequestRow)
            .execution_options(populate_existing=True))
        if row is None:return None
        if (type(row.requested_by) is not uuid.UUID or not row.requested_by.int
                or type(row.job_ref) is not uuid.UUID or not row.job_ref.int
                or type(row.context_snapshot_id) is not uuid.UUID or not row.context_snapshot_id.int
                or type(row.lock_version) is not int or row.lock_version<0):
            raise OutputRequestCancelError("SYSTEM_UNAVAILABLE")
        return OutputRequestCancelFacts(row.output_request_id,row.project_id,row.requested_by,
            row.job_ref,row.context_snapshot_id,row.request_state,row.lock_version)
    def set_state(self,transaction:object,*,facts:OutputRequestCancelFacts,
                  state:str,completed_at:datetime|None)->int:
        if state not in {"CANCEL_REQUESTED","CANCELLED"}:
            raise OutputRequestCancelError("VALIDATION_FAILED")
        row=self._session(transaction).scalar(select(OutputRequestRow).where(
            OutputRequestRow.project_id==facts.project_id,
            OutputRequestRow.output_request_id==facts.output_request_id)
            .with_for_update(of=OutputRequestRow)
            .execution_options(populate_existing=True))
        if (row is None or row.lock_version!=facts.lock_version
                or row.request_state!=facts.state
                or (state=="CANCELLED")!=(completed_at is not None)):
            raise OutputRequestCancelError("CONFLICT_STATE")
        row.request_state=state
        row.completed_at=func.clock_timestamp() if state=="CANCELLED" else None
        row.lock_version+=1
        session=self._session(transaction)
        session.flush()
        session.refresh(row,attribute_names=["request_state","lock_version","completed_at"])
        return row.lock_version
    @staticmethod
    def _session(transaction:object)->Session:
        try:session=transaction.session
        except (AttributeError,RuntimeError):raise OutputRequestCancelError("SYSTEM_UNAVAILABLE") from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise OutputRequestCancelError("SYSTEM_UNAVAILABLE")
        return session
