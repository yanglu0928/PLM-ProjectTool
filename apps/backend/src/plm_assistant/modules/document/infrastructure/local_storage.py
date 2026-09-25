"""Internal local FileObject storage with opaque, scope-bound locators.

Callers must authorize the FileObject before using this adapter. No path is
returned to HTTP clients, and publishing bytes does not change database state.
"""

from __future__ import annotations

import os
import re
import stat
import uuid
from pathlib import Path
from typing import BinaryIO


_UUID_HEX = r"[0-9a-f]{32}"
_LOCATOR = re.compile(
    rf"(?:(?:global|temp/global)/objects/[0-9a-f]{{2}}/{_UUID_HEX}"
    rf"|(?:projects|temp/projects)/{_UUID_HEX}/objects/[0-9a-f]{{2}}/{_UUID_HEX})\Z",
    re.ASCII,
)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LocalStorageError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("local storage unavailable")


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE
    )


def _checked_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise LocalStorageError() from None
    if not stat.S_ISDIR(info.st_mode) or _is_reparse(info):
        raise LocalStorageError()


def _checked_file(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError:
        raise LocalStorageError() from None
    if not stat.S_ISREG(info.st_mode) or _is_reparse(info) or info.st_nlink != 1:
        raise LocalStorageError()
    return info


class LocalFileStorage:
    """Storage-private staging and same-volume no-overwrite promotion."""

    def __init__(self, data_root: Path) -> None:
        if not isinstance(data_root, Path) or not data_root.is_absolute():
            raise LocalStorageError()
        self._root = data_root
        for ancestor in (*reversed(data_root.parents), data_root):
            _checked_directory(ancestor)

    @staticmethod
    def locators(*, scope: str, project_id: uuid.UUID | None,
                 file_object_id: uuid.UUID) -> tuple[str, str]:
        if (type(file_object_id) is not uuid.UUID or file_object_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or (scope == "GLOBAL" and project_id is not None)
                or (scope == "PROJECT" and
                    (type(project_id) is not uuid.UUID or project_id.int == 0))):
            raise LocalStorageError()
        suffix = f"objects/{file_object_id.hex[:2]}/{file_object_id.hex}"
        base = "global" if scope == "GLOBAL" else f"projects/{project_id.hex}"
        return f"temp/{base}/{suffix}", f"{base}/{suffix}"

    def _path(self, locator: str, *, create_parents: bool = False) -> Path:
        if type(locator) is not str or _LOCATOR.fullmatch(locator) is None:
            raise LocalStorageError()
        parts = locator.split("/")
        if parts[-2] != parts[-1][:2]:
            raise LocalStorageError()
        _checked_directory(self._root)
        current = self._root
        for part in parts[:-1]:
            parent = current
            current = current / part
            try:
                entries = {entry.name for entry in os.scandir(parent)}
                if os.name == "nt" and any(name.casefold() == part and name != part
                                           for name in entries):
                    raise LocalStorageError()
                if part not in entries:
                    if not create_parents:
                        raise LocalStorageError()
                    current.mkdir(mode=0o700)
                _checked_directory(current)
            except OSError:
                raise LocalStorageError() from None
        target = current / parts[-1]
        if os.name == "nt":
            try:
                if any(entry.name.casefold() == target.name and entry.name != target.name
                       for entry in os.scandir(current)):
                    raise LocalStorageError()
            except OSError:
                raise LocalStorageError() from None
        return target

    def reserve_staging(self, locator: str) -> BinaryIO:
        if type(locator) is not str or not locator.startswith("temp/"):
            raise LocalStorageError()
        target = self._path(locator, create_parents=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
            return os.fdopen(descriptor, "wb")
        except OSError:
            raise LocalStorageError() from None

    def promote(self, staging_locator: str, final_locator: str) -> None:
        if (not isinstance(staging_locator, str) or not staging_locator.startswith("temp/")
                or final_locator != staging_locator.removeprefix("temp/")):
            raise LocalStorageError()
        source = self._path(staging_locator)
        destination = self._path(final_locator, create_parents=True)
        source_info = _checked_file(source)
        try:
            if source_info.st_dev != destination.parent.stat().st_dev:
                raise LocalStorageError()
            # Windows requires a writable descriptor for FlushFileBuffers/fsync.
            with source.open("r+b") as stream:
                os.fsync(stream.fileno())
            if os.link in os.supports_follow_symlinks:
                os.link(source, destination, follow_symlinks=False)
            else:
                # Windows does not expose follow_symlinks=False for os.link;
                # the source and every parent were checked under the private root.
                os.link(source, destination)
            os.unlink(source)
        except (OSError, NotImplementedError):
            raise LocalStorageError() from None
