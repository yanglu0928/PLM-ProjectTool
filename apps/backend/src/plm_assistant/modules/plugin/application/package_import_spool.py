"""Bounded durable staging for a signed Plugin package import request."""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
import uuid
from dataclasses import dataclass, field
from typing import Iterable

from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage,
    LocalStorageError,
)
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    MAX_PACKAGE_BYTES,
)


_CHUNK_BYTES = 1_048_576


class PluginPackageStageError(RuntimeError):
    """Stable, non-sensitive rejection for a package upload body."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StagedPluginPackage:
    package_upload_id: uuid.UUID
    staging_locator: str = field(repr=False)
    sha256: bytes = field(repr=False)
    size_bytes: int


class PluginPackageImportSpool:
    """Stage request bytes in the application's private storage without loading them all."""

    def __init__(self, *, storage: LocalFileStorage,
                 max_bytes: int = MAX_PACKAGE_BYTES) -> None:
        if (not isinstance(storage, LocalFileStorage)
                or type(max_bytes) is not int
                or not 0 < max_bytes <= MAX_PACKAGE_BYTES):
            raise ValueError("Invalid Plugin package spool policy")
        self._storage = storage
        self._max_bytes = max_bytes

    def receive(self, *, package_upload_id: uuid.UUID, chunks: Iterable[bytes],
                declared_length: int, declared_sha256: bytes) -> StagedPluginPackage:
        if (type(package_upload_id) is not uuid.UUID or package_upload_id.int == 0
                or type(declared_length) is not int or declared_length <= 0
                or type(declared_sha256) is not bytes or len(declared_sha256) != 32):
            raise PluginPackageStageError("VALIDATION_FAILED")
        if declared_length > self._max_bytes:
            raise PluginPackageStageError("FILE_TOO_LARGE")
        try:
            staging_locator, _ = self._storage.locators(
                scope="GLOBAL", project_id=None, file_object_id=package_upload_id,
            )
        except LocalStorageError:
            raise PluginPackageStageError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE") from None

        identity: tuple[int, int] | None = None
        try:
            with self._storage.reserve_staging(staging_locator) as stream:
                before = os.fstat(stream.fileno())
                identity = (before.st_dev, before.st_ino)
                digest = hashlib.sha256()
                total = 0
                for chunk in chunks:
                    if type(chunk) is not bytes or len(chunk) > _CHUNK_BYTES:
                        raise PluginPackageStageError("VALIDATION_FAILED")
                    total += len(chunk)
                    if total > declared_length or total > self._max_bytes:
                        raise PluginPackageStageError("FILE_TOO_LARGE")
                    stream.write(chunk)
                    digest.update(chunk)
                actual_digest = digest.digest()
                if (total != declared_length
                        or not hmac.compare_digest(actual_digest, declared_sha256)):
                    raise PluginPackageStageError("FILE_INTEGRITY_MISMATCH")
                stream.flush()
                os.fsync(stream.fileno())
                after = os.fstat(stream.fileno())
                if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
                        or (after.st_dev, after.st_ino) != identity
                        or after.st_size != total):
                    raise PluginPackageStageError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
            self._storage.verify_content(
                staging_locator,
                expected_sha256=actual_digest,
                expected_size=total,
                max_bytes=self._max_bytes,
            )
            return StagedPluginPackage(
                package_upload_id, staging_locator, actual_digest, total,
            )
        except Exception as exc:
            if identity is not None:
                try:
                    self._storage.discard_new_staging(
                        staging_locator, device=identity[0], inode=identity[1],
                    )
                except LocalStorageError:
                    pass
            if isinstance(exc, PluginPackageStageError):
                raise
            raise PluginPackageStageError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE") from None
