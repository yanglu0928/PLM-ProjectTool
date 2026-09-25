"""Internal local FileObject storage with opaque, scope-bound locators.

Callers must authorize the FileObject before using this adapter. No path is
returned to HTTP clients, and publishing bytes does not change database state.
"""

from __future__ import annotations

import os
import re
import stat
import uuid
import hashlib
import hmac
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class FileContentProof:
    locator: str
    sha256: bytes
    size_bytes: int


@dataclass(frozen=True, slots=True)
class FileRecoveryInspection:
    shape: str


def _optional_info(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise LocalStorageError() from None


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


def _checked_file(path: Path, *, link_count: int = 1) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError:
        raise LocalStorageError() from None
    if not stat.S_ISREG(info.st_mode) or _is_reparse(info) or info.st_nlink != link_count:
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

    def _path(self, locator: str, *, create_parents: bool = False,
              allow_missing_parents: bool = False) -> Path:
        if type(locator) is not str or _LOCATOR.fullmatch(locator) is None:
            raise LocalStorageError()
        parts = locator.split("/")
        if parts[-2] != parts[-1][:2]:
            raise LocalStorageError()
        _checked_directory(self._root)
        current = self._root
        missing_parent = False
        for part in parts[:-1]:
            parent = current
            current = current / part
            if missing_parent:
                continue
            try:
                entries = {entry.name for entry in os.scandir(parent)}
                if os.name == "nt" and any(name.casefold() == part and name != part
                                           for name in entries):
                    raise LocalStorageError()
                if part not in entries:
                    if allow_missing_parents and not create_parents:
                        missing_parent = True
                        continue
                    if not create_parents:
                        raise LocalStorageError()
                    current.mkdir(mode=0o700)
                _checked_directory(current)
            except OSError:
                raise LocalStorageError() from None
        target = current / parts[-1]
        if os.name == "nt" and not missing_parent:
            try:
                if any(entry.name.casefold() == target.name and entry.name != target.name
                       for entry in os.scandir(current)):
                    raise LocalStorageError()
            except OSError:
                raise LocalStorageError() from None
        return target

    def inspect_recovery(self, staging_locator: str, final_locator: str, *,
                         expected_sha256: bytes, expected_size: int,
                         max_bytes: int) -> FileRecoveryInspection:
        """Classify a named STAGED object without mutating either file."""
        if (type(staging_locator) is not str or type(final_locator) is not str
                or not staging_locator.startswith("temp/")
                or final_locator != staging_locator.removeprefix("temp/")
                or type(expected_sha256) is not bytes or len(expected_sha256) != 32
                or type(expected_size) is not int or expected_size < 0
                or type(max_bytes) is not int or max_bytes < 0
                or expected_size > max_bytes):
            raise LocalStorageError()
        staging_path = self._path(staging_locator, allow_missing_parents=True)
        final_path = self._path(final_locator, allow_missing_parents=True)
        stage = _optional_info(staging_path)
        final = _optional_info(final_path)
        if stage is None and final is None:
            return FileRecoveryInspection("NONE")
        if stage is not None and final is None:
            try:
                _checked_file(staging_path)
            except LocalStorageError:
                return FileRecoveryInspection("UNSAFE")
            return FileRecoveryInspection("STAGE_ONLY")
        if stage is None:
            try:
                _checked_file(final_path)
            except LocalStorageError:
                return FileRecoveryInspection("UNSAFE")
            try:
                self.verify_content(
                    final_locator, expected_sha256=expected_sha256,
                    expected_size=expected_size, max_bytes=max_bytes,
                )
            except LocalStorageError:
                return FileRecoveryInspection("FINAL_INVALID")
            return FileRecoveryInspection("FINAL_VERIFIED")
        if (_is_reparse(stage) or _is_reparse(final)
                or not stat.S_ISREG(stage.st_mode)
                or not stat.S_ISREG(final.st_mode)):
            return FileRecoveryInspection("UNSAFE")
        if (stage.st_dev, stage.st_ino) == (final.st_dev, final.st_ino):
            if stage.st_nlink == final.st_nlink == 2:
                return FileRecoveryInspection("LINKED_PAIR")
            return FileRecoveryInspection("UNSAFE")
        if stage.st_nlink == final.st_nlink == 1:
            return FileRecoveryInspection("BOTH_UNRELATED")
        return FileRecoveryInspection("UNSAFE")

    def reserve_staging(self, locator: str) -> BinaryIO:
        if type(locator) is not str or not locator.startswith("temp/"):
            raise LocalStorageError()
        target = self._path(locator, create_parents=True)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
            return os.fdopen(descriptor, "w+b")
        except OSError:
            raise LocalStorageError() from None

    def discard_new_staging(self, locator: str, *, device: int, inode: int) -> None:
        """Remove only the exact unregistered ordinary file created by this request."""
        if (type(locator) is not str or not locator.startswith("temp/")
                or type(device) is not int or type(inode) is not int):
            raise LocalStorageError()
        target = self._path(locator)
        current = _checked_file(target)
        if (current.st_dev, current.st_ino) != (device, inode):
            raise LocalStorageError()
        try:
            os.unlink(target)
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

    def verify_content(self, locator: str, *, expected_sha256: bytes,
                       expected_size: int, max_bytes: int) -> FileContentProof:
        return self._verify_content(
            locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes, link_count=1,
        )

    def _verify_content(self, locator: str, *, expected_sha256: bytes,
                        expected_size: int, max_bytes: int,
                        link_count: int) -> FileContentProof:
        if (type(expected_sha256) is not bytes or len(expected_sha256) != 32
                or type(expected_size) is not int or expected_size < 0
                or type(max_bytes) is not int or max_bytes < 0
                or expected_size > max_bytes):
            raise LocalStorageError()
        path = self._path(locator)
        before = _checked_file(path, link_count=link_count)
        if before.st_size != expected_size:
            raise LocalStorageError()
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (not stat.S_ISREG(opened.st_mode) or _is_reparse(opened)
                        or opened.st_nlink != link_count
                        or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                    raise LocalStorageError()
                digest = hashlib.sha256()
                total = 0
                while chunk := stream.read(min(1_048_576, max_bytes - total + 1)):
                    total += len(chunk)
                    if total > max_bytes or total > expected_size:
                        raise LocalStorageError()
                    digest.update(chunk)
                after_fd = os.fstat(stream.fileno())
            after_path = _checked_file(path, link_count=link_count)
            if ((after_fd.st_dev, after_fd.st_ino, after_fd.st_size,
                 after_fd.st_mtime_ns, after_fd.st_nlink) !=
                (opened.st_dev, opened.st_ino, opened.st_size,
                 opened.st_mtime_ns, opened.st_nlink)
                    or (after_path.st_dev, after_path.st_ino, after_path.st_size,
                        after_path.st_mtime_ns, after_path.st_nlink) !=
                       (opened.st_dev, opened.st_ino, opened.st_size,
                        opened.st_mtime_ns, opened.st_nlink)
                    or total != expected_size
                    or not hmac.compare_digest(digest.digest(), expected_sha256)):
                raise LocalStorageError()
            return FileContentProof(locator, digest.digest(), total)
        except OSError:
            raise LocalStorageError() from None

    def publish_verified(self, staging_locator: str, final_locator: str, *,
                         expected_sha256: bytes, expected_size: int,
                         max_bytes: int) -> FileContentProof:
        if (type(staging_locator) is not str or type(final_locator) is not str
                or not staging_locator.startswith("temp/")
                or final_locator != staging_locator.removeprefix("temp/")):
            raise LocalStorageError()
        self.verify_content(
            staging_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes,
        )
        self.promote(staging_locator, final_locator)
        return self.verify_content(
            final_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes,
        )

    def recover_verified_final(self, staging_locator: str, final_locator: str, *,
                               expected_sha256: bytes, expected_size: int,
                               max_bytes: int) -> FileContentProof:
        """Proof for the final-only crash window; never deletes a staged file."""
        if (type(staging_locator) is not str or type(final_locator) is not str
                or not staging_locator.startswith("temp/")
                or final_locator != staging_locator.removeprefix("temp/")):
            raise LocalStorageError()
        staging_path = self._path(staging_locator)
        if os.path.lexists(staging_path):
            raise LocalStorageError()
        return self.verify_content(
            final_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes,
        )

    def recover_linked_pair(self, staging_locator: str, final_locator: str, *,
                            expected_sha256: bytes, expected_size: int,
                            max_bytes: int) -> FileContentProof:
        """Finish only the exact hard-link-before-unlink promotion window."""
        if (type(staging_locator) is not str or type(final_locator) is not str
                or not staging_locator.startswith("temp/")
                or final_locator != staging_locator.removeprefix("temp/")):
            raise LocalStorageError()
        staging_path = self._path(staging_locator)
        final_path = self._path(final_locator)
        source = _checked_file(staging_path, link_count=2)
        target = _checked_file(final_path, link_count=2)
        if (source.st_dev, source.st_ino) != (target.st_dev, target.st_ino):
            raise LocalStorageError()
        self._verify_content(
            staging_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes, link_count=2,
        )
        self._verify_content(
            final_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes, link_count=2,
        )
        source = _checked_file(staging_path, link_count=2)
        target = _checked_file(final_path, link_count=2)
        if (source.st_dev, source.st_ino) != (target.st_dev, target.st_ino):
            raise LocalStorageError()
        try:
            os.unlink(staging_path)
        except OSError:
            raise LocalStorageError() from None
        return self.verify_content(
            final_locator, expected_sha256=expected_sha256,
            expected_size=expected_size, max_bytes=max_bytes,
        )
