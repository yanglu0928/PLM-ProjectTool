"""Internal Audit file coordinates/proofs, never authority or public download URLs."""
from dataclasses import dataclass
from typing import ContextManager, Protocol
from typing import BinaryIO
from uuid import UUID

MAX_AUDIT_FILE_BYTES = 128 * 1024 * 1024


class AuditFileStorageError(RuntimeError):
    def __init__(self, code="FILE_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AuditFileCoordinate:
    file_id: UUID
    scope: str
    project_id: UUID | None

    def __post_init__(self):
        if (type(self.file_id) is not UUID or not self.file_id.int
                or type(self.scope) is not str or self.scope not in ("PROJECT", "DEPLOYMENT")
                or (self.scope == "DEPLOYMENT" and self.project_id is not None)
                or (self.scope == "PROJECT" and (type(self.project_id) is not UUID or not self.project_id.int))):
            raise AuditFileStorageError()


@dataclass(frozen=True, slots=True)
class AuditFileContent:
    coordinate: AuditFileCoordinate
    sha256: bytes
    size_bytes: int

    def __post_init__(self):
        if type(self.coordinate) is not AuditFileCoordinate:
            raise AuditFileStorageError()
        self.coordinate.__post_init__()
        if (type(self.sha256) is not bytes or len(self.sha256) != 32
                or type(self.size_bytes) is not int or not 0 <= self.size_bytes <= MAX_AUDIT_FILE_BYTES):
            raise AuditFileStorageError()


class AuditFileSink(Protocol):
    def write(self, data: bytes) -> int: ...


class AuditExportFileStoragePort(Protocol):
    def open_snapshot(self, expected: AuditFileContent) -> BinaryIO: ...
    def staging_sink(self, coordinate: AuditFileCoordinate) -> ContextManager[AuditFileSink]: ...
    def verify_staged(self, expected: AuditFileContent) -> AuditFileContent: ...
    def inspect(self, expected: AuditFileContent) -> str: ...
    def promote(self, expected: AuditFileContent, *, mode: str = "new") -> AuditFileContent: ...
