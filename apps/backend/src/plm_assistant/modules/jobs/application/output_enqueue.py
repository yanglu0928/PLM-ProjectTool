"""Output enqueue Port owned by Jobs; joins the caller transaction."""
from __future__ import annotations
import uuid
from typing import Protocol
class OutputJobEnqueueError(RuntimeError):
    def __init__(self,code:str)->None:self.code=code;super().__init__(code)
class OutputJobQueuePort(Protocol):
    def enqueue_output(self,transaction:object,*,project_id:uuid.UUID,output_request_id:uuid.UUID,
        context_snapshot_id:uuid.UUID,actor_id:uuid.UUID,trace_id:uuid.UUID)->uuid.UUID:...
class OutputJobQueue:
    def __init__(self,repository:OutputJobQueuePort)->None:
        if repository is None:raise ValueError("output job repository is required")
        self._repository=repository
    def enqueue_output(self,transaction:object,*,project_id:uuid.UUID,output_request_id:uuid.UUID,
        context_snapshot_id:uuid.UUID,actor_id:uuid.UUID,trace_id:uuid.UUID)->uuid.UUID:
        if any(type(v) is not uuid.UUID or not v.int for v in
               (project_id,output_request_id,context_snapshot_id,actor_id,trace_id)):
            raise OutputJobEnqueueError("VALIDATION_FAILED")
        return self._repository.enqueue_output(transaction,project_id=project_id,
            output_request_id=output_request_id,context_snapshot_id=context_snapshot_id,
            actor_id=actor_id,trace_id=trace_id)
