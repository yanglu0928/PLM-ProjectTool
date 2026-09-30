"""Document-private, write-once bytes for a not-yet-published ParseResultRef.

File promotion is deliberately outside the DB transaction. A failed later
publication may leave an unreachable orphan, never a visible partial result.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from .local_storage import _checked_directory, _checked_file, _is_reparse


_UUID = r"[0-9a-f]{32}"
_LOCATOR = re.compile(
    rf"(?:temp/)?results/(?:global|projects/{_UUID})/[0-9a-f]{{2}}/{_UUID}\.json\Z",
    re.ASCII,
)
_MAX_BYTES = 100_000_000


class ParseResultStorageError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("private parse result storage unavailable")


@dataclass(frozen=True, slots=True)
class StoredParseResult:
    result_ref_id: uuid.UUID
    storage_locator: str
    sha256: bytes
    size_bytes: int

    def __post_init__(self) -> None:
        if (type(self.result_ref_id) is not uuid.UUID or self.result_ref_id.int == 0
                or type(self.storage_locator) is not str
                or _LOCATOR.fullmatch(self.storage_locator) is None
                or self.storage_locator.startswith("temp/")
                or self.storage_locator.split("/")[-1] != f"{self.result_ref_id.hex}.json"
                or type(self.sha256) is not bytes or len(self.sha256) != 32
                or type(self.size_bytes) is not int
                or not 1 <= self.size_bytes <= _MAX_BYTES):
            raise ParseResultStorageError()


class LocalParseResultStorage:
    def __init__(self, data_root: Path) -> None:
        if not isinstance(data_root, Path) or not data_root.is_absolute():
            raise ParseResultStorageError()
        self._root = data_root
        try:
            for ancestor in (*reversed(data_root.parents), data_root):
                _checked_directory(ancestor)
        except Exception:
            raise ParseResultStorageError() from None

    @staticmethod
    def locators(*, scope: str, project_id: uuid.UUID | None,
                 result_ref_id: uuid.UUID) -> tuple[str, str]:
        if (type(result_ref_id) is not uuid.UUID or result_ref_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or (scope == "GLOBAL" and project_id is not None)
                or (scope == "PROJECT" and (type(project_id) is not uuid.UUID
                                             or project_id.int == 0))):
            raise ParseResultStorageError()
        base = "global" if scope == "GLOBAL" else f"projects/{project_id.hex}"
        final = f"results/{base}/{result_ref_id.hex[:2]}/{result_ref_id.hex}.json"
        return f"temp/{final}", final

    def write_once(self, *, scope: str, project_id: uuid.UUID | None,
                   result_ref_id: uuid.UUID, content: bytes) -> StoredParseResult:
        if type(content) is not bytes or not 1 <= len(content) <= _MAX_BYTES:
            raise ParseResultStorageError()
        stage, final = self.locators(scope=scope, project_id=project_id,
                                     result_ref_id=result_ref_id)
        digest = hashlib.sha256(content).digest()
        try:
            stage_path = self._path(stage, create_parents=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(stage_path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self._read(stage, digest, len(content))
            final_path = self._path(final, create_parents=True)
            source = _checked_file(stage_path)
            if source.st_dev != final_path.parent.stat().st_dev:
                raise ParseResultStorageError()
            if os.link in os.supports_follow_symlinks:
                os.link(stage_path, final_path, follow_symlinks=False)
            else:
                os.link(stage_path, final_path)
            os.unlink(stage_path)
            self._read(final, digest, len(content))
            return StoredParseResult(result_ref_id, final, digest, len(content))
        except Exception:
            raise ParseResultStorageError() from None

    def read_verified(self, *, scope: str, project_id: uuid.UUID | None,
                      result_ref_id: uuid.UUID, expected_locator: str,
                      expected_sha256: bytes, expected_size: int) -> bytes:
        _, final = self.locators(scope=scope, project_id=project_id,
                                 result_ref_id=result_ref_id)
        if expected_locator != final:
            raise ParseResultStorageError()
        return self._read(final, expected_sha256, expected_size)

    def _read(self, locator: str, digest: bytes, size: int) -> bytes:
        if (type(digest) is not bytes or len(digest) != 32
                or type(size) is not int or not 1 <= size <= _MAX_BYTES):
            raise ParseResultStorageError()
        try:
            path = self._path(locator)
            before = _checked_file(path)
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (not stat.S_ISREG(opened.st_mode) or _is_reparse(opened)
                        or opened.st_nlink != 1 or opened.st_size != size
                        or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                    raise ParseResultStorageError()
                content = stream.read(size + 1)
            after = _checked_file(path)
            if (len(content) != size or not hmac.compare_digest(hashlib.sha256(content).digest(), digest)
                    or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                raise ParseResultStorageError()
            return content
        except Exception:
            raise ParseResultStorageError() from None

    def _path(self, locator: str, *, create_parents: bool = False) -> Path:
        if type(locator) is not str or _LOCATOR.fullmatch(locator) is None:
            raise ParseResultStorageError()
        parts = locator.split("/")
        if parts[-2] != parts[-1][:2]:
            raise ParseResultStorageError()
        try:
            _checked_directory(self._root)
            current = self._root
            for part in parts[:-1]:
                entries = {entry.name for entry in os.scandir(current)}
                if os.name == "nt" and any(name.casefold() == part and name != part
                                           for name in entries):
                    raise ParseResultStorageError()
                current = current / part
                if part not in entries:
                    if not create_parents:
                        raise ParseResultStorageError()
                    current.mkdir(mode=0o700)
                _checked_directory(current)
            target = current / parts[-1]
            if os.name == "nt" and any(entry.name.casefold() == target.name
                                       and entry.name != target.name
                                       for entry in os.scandir(current)):
                raise ParseResultStorageError()
            return target
        except Exception:
            raise ParseResultStorageError() from None
