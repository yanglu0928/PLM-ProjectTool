"""Document-owned internal ParseResult storage proof and publication contract."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime


_LOCATOR = re.compile(
    r"results/(?:global|projects/[0-9a-f]{32})/[0-9a-f]{2}/[0-9a-f]{32}\.json\Z"
)


class ParsePublishError(RuntimeError):
    def __init__(self, code: str = "PARSER_PUBLISH_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StoredParseResult:
    result_ref_id: uuid.UUID
    storage_locator: str
    sha256: bytes = field(repr=False)
    size_bytes: int

    def __post_init__(self) -> None:
        if (type(self.result_ref_id) is not uuid.UUID or self.result_ref_id.int == 0
                or type(self.storage_locator) is not str
                or _LOCATOR.fullmatch(self.storage_locator) is None
                or self.storage_locator.split("/")[-1] != f"{self.result_ref_id.hex}.json"
                or self.storage_locator.split("/")[-2] != self.result_ref_id.hex[:2]
                or type(self.sha256) is not bytes or len(self.sha256) != 32
                or type(self.size_bytes) is not int
                or not 1 <= self.size_bytes <= 100_000_000):
            raise ParsePublishError("PARSER_RESULT_PROOF_INVALID")


@dataclass(frozen=True, slots=True)
class ParseSuccessRequest:
    parse_record_id: uuid.UUID
    job_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    parser_profile: str
    parser_version: str
    attempt_no: int
    file: StoredParseResult

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    self.parse_record_id, self.job_id, self.document_version_id))
                or self.scope not in ("GLOBAL", "PROJECT")
                or (self.scope == "GLOBAL" and self.project_id is not None)
                or (self.scope == "PROJECT" and
                    (type(self.project_id) is not uuid.UUID or self.project_id.int == 0))
                or type(self.parser_profile) is not str or not self.parser_profile
                or type(self.parser_version) is not str or not self.parser_version
                or type(self.attempt_no) is not int or self.attempt_no != 1
                or type(self.file) is not StoredParseResult):
            raise ParsePublishError("VALIDATION_FAILED")
        self.file.__post_init__()
        prefix = ("results/global" if self.scope == "GLOBAL"
                  else f"results/projects/{self.project_id.hex}")
        if self.file.storage_locator != (
                f"{prefix}/{self.file.result_ref_id.hex[:2]}/"
                f"{self.file.result_ref_id.hex}.json"):
            raise ParsePublishError("PARSER_RESULT_PROOF_INVALID")


@dataclass(frozen=True, slots=True)
class PublishedParseResult:
    parse_record_id: uuid.UUID
    result_ref_id: uuid.UUID
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.parse_record_id) is not uuid.UUID or self.parse_record_id.int == 0
                or type(self.result_ref_id) is not uuid.UUID or self.result_ref_id.int == 0
                or type(self.completed_at) is not datetime
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise ParsePublishError()
