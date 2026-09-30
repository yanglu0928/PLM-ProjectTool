"""Document-owned internal ParseRecord start contract; no Job authority itself."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


class ParseAttemptError(RuntimeError):
    def __init__(self, code: str = "PARSER_ATTEMPT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DocumentParseAttemptRequest:
    document_version_id: uuid.UUID
    content_sha256: bytes = field(repr=False)
    size_bytes: int
    detected_mime: str
    parser_profile: str
    parser_version: str

    def __post_init__(self) -> None:
        if (type(self.document_version_id) is not uuid.UUID or self.document_version_id.int == 0
                or type(self.content_sha256) is not bytes or len(self.content_sha256) != 32
                or type(self.size_bytes) is not int or not 0 <= self.size_bytes <= 100_000_000
                or type(self.detected_mime) is not str or not self.detected_mime
                or type(self.parser_profile) is not str or not self.parser_profile
                or type(self.parser_version) is not str or not self.parser_version):
            raise ParseAttemptError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class StartedParseAttempt:
    parse_record_id: uuid.UUID
    job_id: uuid.UUID
    document_version_id: uuid.UUID
    parser_profile: str
    parser_version: str
    attempt_no: int
    started_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    self.parse_record_id, self.job_id, self.document_version_id))
                or type(self.parser_profile) is not str or not self.parser_profile
                or type(self.parser_version) is not str or not self.parser_version
                or type(self.attempt_no) is not int or self.attempt_no != 1
                or type(self.started_at) is not datetime
                or self.started_at.tzinfo is None
                or self.started_at.utcoffset() is None):
            raise ParseAttemptError()
