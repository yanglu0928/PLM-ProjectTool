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
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


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


@dataclass(frozen=True, slots=True)
class StagingSnapshot:
    device: int
    inode: int
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class StagingCandidate:
    scope: str
    project_id: uuid.UUID | None
    upload_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class StagingScan:
    candidates: tuple[StagingCandidate, ...]
    skipped: int
    inspected: int
    truncated: bool


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


def _lock_staging(descriptor: int) -> None:
    """Nonblocking process-owned lock; released when the descriptor closes."""
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError):
        raise LocalStorageError() from None


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

    def scan_staging_candidates(self, *, max_entries: int = 10_000,
                                max_candidates: int = 500) -> StagingScan:
        """Bounded read-only inventory of canonical upload staging entries."""
        if (type(max_entries) is not int or not 1 <= max_entries <= 100_000
                or type(max_candidates) is not int or not 1 <= max_candidates <= max_entries):
            raise LocalStorageError()
        inspected = skipped = 0
        truncated = False
        candidates: list[StagingCandidate] = []

        def children(directory: Path) -> Iterator[Path]:
            nonlocal inspected, truncated
            if _optional_info(directory) is None:
                return
            _checked_directory(directory)
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if inspected >= max_entries or len(candidates) >= max_candidates:
                            truncated = True
                            return
                        inspected += 1
                        yield Path(entry.path)
            except OSError:
                raise LocalStorageError() from None

        temp = self._root / "temp"
        if _optional_info(temp) is None:
            return StagingScan((), 0, 0, False)
        _checked_directory(temp)
        global_root = temp / "global"
        if _optional_info(global_root) is not None:
            _checked_directory(global_root)
        roots: list[tuple[Path, str, uuid.UUID | None]] = [
            (global_root / "objects", "GLOBAL", None),
        ]
        projects = temp / "projects"
        for project_dir in children(projects):
            try:
                if not re.fullmatch(_UUID_HEX, project_dir.name, re.ASCII):
                    raise LocalStorageError()
                project_id = uuid.UUID(hex=project_dir.name)
                if project_id.int == 0:
                    raise LocalStorageError()
                _checked_directory(project_dir)
                roots.append((project_dir / "objects", "PROJECT", project_id))
            except (LocalStorageError, ValueError):
                skipped += 1
        for objects, scope, project_id in roots:
            if truncated:
                break
            for bucket in children(objects):
                try:
                    if not re.fullmatch(r"[0-9a-f]{2}", bucket.name, re.ASCII):
                        raise LocalStorageError()
                    _checked_directory(bucket)
                except LocalStorageError:
                    skipped += 1
                    continue
                for path in children(bucket):
                    try:
                        if not re.fullmatch(_UUID_HEX, path.name, re.ASCII):
                            raise LocalStorageError()
                        upload_id = uuid.UUID(hex=path.name)
                        locator, _ = self.locators(
                            scope=scope, project_id=project_id, file_object_id=upload_id,
                        )
                        if path != self._root / locator:
                            raise LocalStorageError()
                        _checked_file(path)
                        candidates.append(StagingCandidate(scope, project_id, upload_id))
                    except (LocalStorageError, ValueError):
                        skipped += 1
                    if truncated or len(candidates) >= max_candidates:
                        truncated = len(candidates) >= max_candidates or truncated
                        break
                if truncated:
                    break
        return StagingScan(tuple(candidates), skipped, inspected, truncated)

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
            try:
                _lock_staging(descriptor)
                return os.fdopen(descriptor, "w+b")
            except Exception:
                os.close(descriptor)
                raise
        except OSError:
            raise LocalStorageError() from None

    @contextmanager
    def locked_existing_staging(self, locator: str) -> Iterator[BinaryIO | None]:
        """Hold the writer-compatible lock while inspecting an existing stage."""
        if type(locator) is not str or not locator.startswith("temp/"):
            raise LocalStorageError()
        target = self._path(locator, allow_missing_parents=True)
        before = _optional_info(target)
        if before is None:
            yield None
            return
        before = _checked_file(target)
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags)
        except OSError:
            raise LocalStorageError() from None
        try:
            _lock_staging(descriptor)
            opened = os.fstat(descriptor)
            after = _checked_file(target)
            if (not stat.S_ISREG(opened.st_mode) or _is_reparse(opened)
                    or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                    or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)):
                raise LocalStorageError()
            with os.fdopen(descriptor, "r+b") as stream:
                descriptor = -1
                yield stream
        finally:
            if descriptor != -1:
                os.close(descriptor)

    def check_locked_staging(self, locator: str, stream: BinaryIO, *,
                             device: int, inode: int, size: int) -> None:
        if (type(locator) is not str or not locator.startswith("temp/")
                or type(device) is not int or type(inode) is not int
                or type(size) is not int or size < 0):
            raise LocalStorageError()
        opened = os.fstat(stream.fileno())
        current = _checked_file(self._path(locator))
        if (not stat.S_ISREG(opened.st_mode) or _is_reparse(opened)
                or opened.st_nlink != 1 or current.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (device, inode)
                or (current.st_dev, current.st_ino) != (device, inode)
                or opened.st_size != size or current.st_size != size
                or opened.st_mtime_ns != current.st_mtime_ns):
            raise LocalStorageError()

    def inspect_staging_for_cleanup(self, locator: str) -> StagingSnapshot | None:
        """Observe a private staged file only when no upload owns its OS lock."""
        with self.locked_existing_staging(locator) as stream:
            if stream is None:
                return None
            info = os.fstat(stream.fileno())
            self.check_locked_staging(
                locator, stream, device=info.st_dev, inode=info.st_ino,
                size=info.st_size,
            )
            return StagingSnapshot(info.st_dev, info.st_ino,
                                   info.st_size, info.st_mtime_ns)

    def discard_stale_staging(self, locator: str, *, snapshot: StagingSnapshot,
                              cutoff_ns: int) -> None:
        """Delete only an unchanged candidate; caller must prove DB eligibility."""
        if (type(snapshot) is not StagingSnapshot or type(cutoff_ns) is not int
                or cutoff_ns <= 0 or snapshot.modified_ns > cutoff_ns):
            raise LocalStorageError()
        with self.locked_existing_staging(locator) as stream:
            if stream is None:
                raise LocalStorageError()
            info = os.fstat(stream.fileno())
            if ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) !=
                    (snapshot.device, snapshot.inode, snapshot.size_bytes,
                     snapshot.modified_ns)):
                raise LocalStorageError()
            self.check_locked_staging(
                locator, stream, device=snapshot.device, inode=snapshot.inode,
                size=snapshot.size_bytes,
            )
        # Windows cannot unlink while this handle is locked/open. The private
        # storage root and final inode/mtime check narrow the release window.
        path = self._path(locator)
        current = _checked_file(path)
        if ((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
                (snapshot.device, snapshot.inode, snapshot.size_bytes,
                 snapshot.modified_ns)
                or current.st_mtime_ns > cutoff_ns):
            raise LocalStorageError()
        try:
            os.unlink(path)
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
