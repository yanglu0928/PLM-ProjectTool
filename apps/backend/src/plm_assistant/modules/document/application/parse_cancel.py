"""Document-owned current ParseRecord cancellation, including uncertain start receipts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from .parse_attempt import StartedParseAttempt


class ParseCancelError(RuntimeError):
    def __init__(self, code: str = "PARSER_ATTEMPT_CONFLICT") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParseCancelRequest:
    job_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    attempt_no: int
    started: StartedParseAttempt | None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (self.job_id, self.document_version_id))
                or self.scope not in {"GLOBAL", "PROJECT"}
                or (self.scope == "GLOBAL" and self.project_id is not None)
                or (self.scope == "PROJECT" and
                    (type(self.project_id) is not uuid.UUID or self.project_id.int == 0))
                or type(self.attempt_no) is not int or not 1 <= self.attempt_no <= 3
                or (self.started is not None and type(self.started) is not StartedParseAttempt)):
            raise ParseCancelError("VALIDATION_FAILED")
        if self.started is not None:
            self.started.__post_init__()
            if ((self.started.job_id, self.started.document_version_id,
                 self.started.attempt_no)
                    != (self.job_id, self.document_version_id, self.attempt_no)):
                raise ParseCancelError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class CancelledParseAttempt:
    parse_record_id: uuid.UUID
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.parse_record_id) is not uuid.UUID or self.parse_record_id.int == 0
                or type(self.completed_at) is not datetime
                or self.completed_at.tzinfo is None):
            raise ParseCancelError()
