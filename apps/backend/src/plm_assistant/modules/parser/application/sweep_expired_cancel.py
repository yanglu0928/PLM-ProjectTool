"""One bounded Parser cancel recovery step over read-only database hints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock

from plm_assistant.modules.jobs.application.parse_cancel_scan import (
    ExpiredParserCancelCandidate, ExpiredParserCancelCursor,
)

from .cancel_attempt import ParserCancellationError, ParserCancellationOutcome
from .prepare_input import ParserInputCommand


@dataclass(frozen=True, slots=True)
class ParserCancelSweepOutcome:
    kind: str
    job_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (self.kind not in {"IDLE", "RECOVERED", "SUPERSEDED"}
                or (self.kind == "IDLE") != (self.job_id is None)
                or (self.job_id is not None and
                    (type(self.job_id) is not uuid.UUID or self.job_id.int == 0))):
            raise ParserCancellationError()


class ParserExpiredCancelSweep:
    def __init__(self, *, unit_of_work, candidates, recovery, system_actor):
        if (any(value is None for value in (
                unit_of_work, candidates, recovery, system_actor))
                or getattr(recovery, "_system_actor", None) is not system_actor):
            raise ValueError("Same controlled Parser recovery identity required")
        self._uow, self._candidates, self._recovery = unit_of_work, candidates, recovery
        self._actor = system_actor
        self._cursor: ExpiredParserCancelCursor | None = None
        self._lock = Lock()

    def _identity(self) -> uuid.UUID:
        try:
            value = self._actor.assert_current()
            if type(value) is not uuid.UUID or value.int == 0:
                raise ValueError()
            return value
        except Exception:
            raise ParserCancellationError("SYSTEM_ACTOR_UNAVAILABLE") from None

    def run_next(self) -> ParserCancelSweepOutcome:
        if not self._lock.acquire(blocking=False):
            raise ParserCancellationError("PARSER_SWEEP_BUSY")
        try:
            identity = self._identity()
            try:
                with self._uow() as tx:
                    candidate = self._candidates.scan_next(tx, after=self._cursor)
                    if candidate is not None:
                        if type(candidate) is not ExpiredParserCancelCandidate:
                            raise ParserCancellationError()
                        candidate.__post_init__()
                    if self._identity() != identity:
                        raise ParserCancellationError("SYSTEM_ACTOR_UNAVAILABLE")
            except ParserCancellationError:
                raise
            except Exception:
                raise ParserCancellationError() from None
            if candidate is None:
                self._cursor = None
                return ParserCancelSweepOutcome("IDLE")
            self._cursor = candidate.cursor
            command = ParserInputCommand(candidate.cursor.job_id,
                candidate.fencing_token, candidate.worker_ref)
            try:
                value = self._recovery.recover(command=command)
                if type(value) is not ParserCancellationOutcome:
                    raise ParserCancellationError()
            except Exception as exc:
                # The commit may have succeeded while its acknowledgement was lost.
                try:
                    verified = self._recovery.verify_committed(command=command)
                    if type(verified) is not ParserCancellationOutcome:
                        raise ParserCancellationError()
                    return ParserCancelSweepOutcome("RECOVERED", command.job_id)
                except Exception:
                    if (isinstance(exc, ParserCancellationError)
                            and exc.code == "STALE_LEASE"):
                        return ParserCancelSweepOutcome("SUPERSEDED", command.job_id)
                    if isinstance(exc, ParserCancellationError):
                        raise exc
                    raise ParserCancellationError() from None
            verified = self._recovery.verify_committed(command=command)
            if verified != value:
                raise ParserCancellationError()
            return ParserCancelSweepOutcome("RECOVERED", command.job_id)
        finally:
            self._lock.release()
