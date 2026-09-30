"""Windows process self-report for diagnostics, never quiescence authority."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from plm_assistant import __version__
from .windows_process_inventory import _windows_sid_reader


_ROLES = frozenset({"API", "AUDIT_WORKER", "PARSER_WORKER"})
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class RuntimeProcessIdentityError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("RUNTIME_PROCESS_IDENTITY_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class RuntimeProcessIdentity:
    role: str
    pid: int
    registered_at_utc: str
    package_version: str
    code_sha256: str
    owner_sid: str
    executable_path: str
    nonce: str


def package_code_digest(root: Path) -> str:
    """Hash packaged source/resources, not mutable pycache or customer data."""
    if not isinstance(root, Path) or not root.is_dir():
        raise RuntimeProcessIdentityError()
    digest = hashlib.sha256()
    count = total_bytes = 0
    try:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(root)
            if "__pycache__" in relative.parts or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_symlink():
                raise RuntimeProcessIdentityError()
            if not path.is_file():
                continue
            info = path.stat()
            count += 1
            total_bytes += info.st_size
            if (count > 5000 or info.st_size > 16 * 1024 * 1024
                    or total_bytes > 128 * 1024 * 1024):
                raise RuntimeProcessIdentityError()
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = path.stat()
            if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                raise RuntimeProcessIdentityError()
            digest.update(b"\0")
        if count == 0:
            raise RuntimeProcessIdentityError()
        return digest.hexdigest()
    except Exception:
        raise RuntimeProcessIdentityError() from None


def _checked_directory(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & _REPARSE)):
        raise RuntimeProcessIdentityError()


def _identity(role: str) -> RuntimeProcessIdentity:
    package_root = Path(__file__).resolve(strict=True).parents[3]
    version = metadata.version("plm-project-tool-backend")
    if version != __version__:
        raise RuntimeProcessIdentityError()
    owner_sid = _windows_sid_reader()(os.getpid())
    if owner_sid is None:
        raise RuntimeProcessIdentityError()
    return RuntimeProcessIdentity(
        role=role, pid=os.getpid(),
        registered_at_utc=datetime.now(timezone.utc).isoformat(),
        package_version=version, code_sha256=package_code_digest(package_root),
        owner_sid=owner_sid,
        executable_path=str(Path(sys.executable).resolve(strict=True)),
        nonce=uuid4().hex,
    )


@contextmanager
def register_runtime_process(role: str, data_root: Path) -> Iterator[RuntimeProcessIdentity]:
    """Own only the exact marker created by this process; leave crash evidence."""
    if (sys.platform != "win32" or role not in _ROLES
            or not isinstance(data_root, Path) or not data_root.is_absolute()):
        raise RuntimeProcessIdentityError()
    marker = None
    created = False
    created_directory = False
    try:
        _checked_directory(data_root)
        directory = data_root / ".plm-runtime-processes"
        created_directory = not directory.exists()
        directory.mkdir(mode=0o700, exist_ok=True)
        _checked_directory(directory)
        identity = _identity(role)
        marker = directory / f"{role.lower()}-{identity.pid}-{identity.nonce}.json"
        serialized = json.dumps({"schema_version": 1, **asdict(identity)},
                                sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(serialized) > 2048:
            raise RuntimeProcessIdentityError()
        stream = marker.open("xb")
        created = True
        with stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        info = marker.lstat()
    except Exception:
        if created and marker is not None:
            try:
                marker.unlink(missing_ok=True)
            except OSError:
                pass
        if created_directory:
            try:
                directory.rmdir()
            except OSError:
                pass
        raise RuntimeProcessIdentityError() from None
    try:
        yield identity
    except BaseException:
        # An uncertain shutdown leaves a marker for OS/PID reconciliation.
        raise
    else:
        try:
            current = marker.lstat()
            if ((current.st_dev, current.st_ino) != (info.st_dev, info.st_ino)
                    or current.st_size != len(serialized)
                    or marker.read_bytes() != serialized):
                raise RuntimeProcessIdentityError()
            marker.unlink()
            if created_directory:
                try:
                    directory.rmdir()
                except OSError:
                    pass
        except Exception:
            raise RuntimeProcessIdentityError() from None
