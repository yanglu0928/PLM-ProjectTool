"""Transaction-scoped Jobs-owned cancellation command for OutputGenerate jobs."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
class OutputJobCancelError(RuntimeError):
    def __init__(self, code: str = "JOB_STORE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)
@dataclass(frozen=True, slots=True)
class OutputJobCancelResult:
    job_id: uuid.UUID
    state: str
    changed: bool
    def __post_init__(self) -> None:
        if (type(self.job_id) is not uuid.UUID or not self.job_id.int
                or self.state not in {"CANCEL_REQUESTED", "CANCELLED", "SUCCEEDED", "FAILED"}
                or type(self.changed) is not bool
                or self.changed and self.state in {"SUCCEEDED", "FAILED"}):
            raise OutputJobCancelError()
class OutputJobCancellationPort:
    """Narrow Jobs-owned port; caller owns the UOW and must commit both aggregates."""
    def cancel_output(self, transaction: object, *, project_id: uuid.UUID,
                      job_id: uuid.UUID, output_request_id: uuid.UUID,
                      context_snapshot_id: uuid.UUID, actor_id: uuid.UUID,
                      reason: str) -> OutputJobCancelResult:
        raise NotImplementedError
class OutputJobCancellation:
    def __init__(self, repository: OutputJobCancellationPort) -> None:
        if repository is None:
            raise ValueError("Output Job cancellation repository is required")
        self._repository = repository
    def cancel_output(self, transaction: object, *, project_id: uuid.UUID,
                      job_id: uuid.UUID, output_request_id: uuid.UUID,
                      context_snapshot_id: uuid.UUID, actor_id: uuid.UUID,
                      reason: str) -> OutputJobCancelResult:
        values=(project_id,job_id,output_request_id,context_snapshot_id,actor_id)
        if any(type(v) is not uuid.UUID or not v.int for v in values):
            raise OutputJobCancelError("VALIDATION_FAILED")
        if (type(reason) is not str or not 1 <= len(reason) <= 1024
                or reason.strip() != reason):
            raise OutputJobCancelError("VALIDATION_FAILED")
        try:
            result=self._repository.cancel_output(transaction,project_id=project_id,
                job_id=job_id,output_request_id=output_request_id,
                context_snapshot_id=context_snapshot_id,actor_id=actor_id,reason=reason)
            if type(result) is not OutputJobCancelResult or result.job_id != job_id:
                raise OutputJobCancelError()
            result.__post_init__()
            return result
        except OutputJobCancelError:
            raise
        except Exception:
            raise OutputJobCancelError() from None
