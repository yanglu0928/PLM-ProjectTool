"""Document-owned failure transition for an already-started ParseRecord."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from .parse_attempt import StartedParseAttempt


class ParseFailureError(RuntimeError):
    def __init__(self, code: str = "PARSER_ATTEMPT_CONFLICT") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParseFailureRequest:
    started: StartedParseAttempt
    scope: str
    project_id: uuid.UUID | None
    error_code: str
    retryable: bool

    def __post_init__(self) -> None:
        if (type(self.started) is not StartedParseAttempt
                or self.scope not in ("GLOBAL", "PROJECT")
                or (self.scope == "GLOBAL" and self.project_id is not None)
                or (self.scope == "PROJECT" and
                    (type(self.project_id) is not uuid.UUID or self.project_id.int == 0))
                or type(self.error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.retryable) is not bool):
            raise ParseFailureError("VALIDATION_FAILED")
        self.started.__post_init__()


@dataclass(frozen=True, slots=True)
class FailedParseAttempt:
    parse_record_id: uuid.UUID
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.parse_record_id) is not uuid.UUID or self.parse_record_id.int == 0
                or type(self.completed_at) is not datetime
                or self.completed_at.tzinfo is None):
            raise ParseFailureError()
