"""OutputRequest persistence; never opens or commits a transaction."""
from __future__ import annotations
import uuid
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from plm_assistant.modules.output.application.create_request import (
    CreatedOutputRequest,CreateOutputRequest,OutputRequestError,ResolvedOutputContext)
from plm_assistant.modules.output.infrastructure.orm import OutputContextSnapshotRow,OutputRequestRow
class SqlAlchemyOutputRequestRepository:
    def lock_generation(self,transaction:object,*,project_id:uuid.UUID,identity_fingerprint:bytes)->None:
        session=self._session(transaction)
        lock_key=f"{project_id}:{identity_fingerprint.hex()}"
        session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key,0))))
    def find_generation(self,transaction:object,*,project_id:uuid.UUID,output_type:str,
        input_fingerprint:bytes,template_version_ref:uuid.UUID,output_policy_ref:str,
        generation_no:int)->CreatedOutputRequest|None:
        session=self._session(transaction)
        row=session.execute(select(OutputRequestRow).where(
            OutputRequestRow.project_id==project_id,OutputRequestRow.output_type==output_type,
            OutputRequestRow.input_fingerprint==input_fingerprint,
            OutputRequestRow.template_version_ref==template_version_ref,
            OutputRequestRow.output_policy_ref==output_policy_ref,
            OutputRequestRow.generation_no==generation_no).with_for_update()).scalar_one_or_none()
        return None if row is None else self._view(row)
    def create(self,transaction:object,*,command:CreateOutputRequest,actor_id:uuid.UUID,
        context:ResolvedOutputContext,input_fingerprint:bytes)->uuid.UUID:
        session=self._session(transaction);snapshot_id,request_id=uuid.uuid4(),uuid.uuid4()
        session.add(OutputContextSnapshotRow(context_snapshot_id=snapshot_id,
            project_id=command.project_id,
            source_version_refs=[str(v) for v in context.source_version_refs],
            context_payload=context.context_payload,context_fingerprint=context.context_fingerprint,
            created_by=actor_id));session.flush()
        session.add(OutputRequestRow(output_request_id=request_id,project_id=command.project_id,
            output_type=command.output_type,template_version_ref=command.template_version_ref,
            source_version_refs=[str(v) for v in context.source_version_refs],
            output_policy_ref=command.output_policy_ref,plugin_operation=command.plugin_operation,
            context_snapshot_id=snapshot_id,input_fingerprint=input_fingerprint,
            generation_no=1,request_state="REQUESTED",idempotency_key=str(request_id),
            trace_id=command.trace_id,requested_by=actor_id))
        session.flush();return request_id
    def snapshot_id(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID)->uuid.UUID:
        value=self._session(transaction).execute(select(OutputRequestRow.context_snapshot_id).where(
            OutputRequestRow.project_id==project_id,
            OutputRequestRow.output_request_id==output_request_id)).scalar_one_or_none()
        if type(value) is not uuid.UUID or not value.int:raise OutputRequestError("SYSTEM_UNAVAILABLE")
        return value
    def attach_job(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID,job_id:uuid.UUID)->None:
        session=self._session(transaction)
        row=session.execute(select(OutputRequestRow).where(
            OutputRequestRow.project_id==project_id,
            OutputRequestRow.output_request_id==output_request_id).with_for_update()).scalar_one_or_none()
        if row is None or row.job_ref is not None:raise OutputRequestError("SYSTEM_UNAVAILABLE")
        row.job_ref=job_id;row.request_state="QUEUED";row.lock_version+=1;session.flush()
    def get(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID)->CreatedOutputRequest|None:
        row=self._session(transaction).execute(select(OutputRequestRow).where(
            OutputRequestRow.project_id==project_id,
            OutputRequestRow.output_request_id==output_request_id)).scalar_one_or_none()
        return None if row is None else self._view(row)
    @staticmethod
    def _view(row:OutputRequestRow)->CreatedOutputRequest:
        if type(row.job_ref) is not uuid.UUID or not row.job_ref.int or row.request_state!="QUEUED":
            raise OutputRequestError("SYSTEM_UNAVAILABLE")
        return CreatedOutputRequest(row.output_request_id,row.project_id,row.job_ref,row.request_state,202)
    @staticmethod
    def _session(transaction:object)->Session:
        try:session=transaction.session
        except (AttributeError,RuntimeError):raise OutputRequestError("OUTPUT_STORE_UNAVAILABLE") from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise OutputRequestError("OUTPUT_STORE_UNAVAILABLE")
        return session
