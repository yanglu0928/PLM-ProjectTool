"""Single-host, cross-process upload I/O gate backed by private local files."""

from __future__ import annotations

import os
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage


_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class UploadGateError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("upload operation gate unavailable")


def _regular_private_file(path: Path, descriptor: int) -> bool:
    try:
        opened, linked = os.fstat(descriptor), path.lstat()
    except OSError:
        return False
    return (stat.S_ISREG(opened.st_mode) and stat.S_ISREG(linked.st_mode)
            and opened.st_nlink == linked.st_nlink == 1
            and not getattr(linked, "st_file_attributes", 0) & _REPARSE
            and (opened.st_dev, opened.st_ino) == (linked.st_dev, linked.st_ino))


def _lock(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_UN)


class LocalUploadOperationGate:
    """Keep one OS lock handle open across all short transactions and file I/O."""

    def __init__(self, data_root: Path) -> None:
        try:
            LocalFileStorage(data_root)
            gate_root = data_root / ".upload-gates"
            gate_root.mkdir(mode=0o700, exist_ok=True)
            info = gate_root.lstat()
            if (not stat.S_ISDIR(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & _REPARSE):
                raise UploadGateError()
        except Exception:
            raise UploadGateError() from None
        self._data_root, self._root = data_root, gate_root

    @contextmanager
    def hold(self, upload_id: uuid.UUID) -> Iterator[None]:
        if type(upload_id) is not uuid.UUID or upload_id.int == 0:
            raise UploadGateError()
        # A fixed number of lock files bounds directory growth. Bucket
        # collision only serializes otherwise independent upload operations.
        path = self._root / f"{upload_id.hex[:2]}.lock"
        descriptor = -1
        locked = False
        try:
            LocalFileStorage(self._data_root)
            gate_info = self._root.lstat()
            if (not stat.S_ISDIR(gate_info.st_mode)
                    or getattr(gate_info, "st_file_attributes", 0) & _REPARSE):
                raise UploadGateError()
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR
                                 | getattr(os, "O_BINARY", 0)
                                 | getattr(os, "O_NOINHERIT", 0)
                                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
            if not _regular_private_file(path, descriptor):
                raise UploadGateError()
            _lock(descriptor)
            locked = True
            if not _regular_private_file(path, descriptor):
                raise UploadGateError()
        except Exception:
            if descriptor >= 0:
                if locked:
                    try:
                        _unlock(descriptor)
                    except OSError:
                        pass
                os.close(descriptor)
            raise UploadGateError() from None
        try:
            yield
        finally:
            try:
                _unlock(descriptor)
            except OSError:
                raise UploadGateError() from None
            finally:
                os.close(descriptor)
