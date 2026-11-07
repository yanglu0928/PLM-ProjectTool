"""Plugin-owned contract for durable package verification Job enqueue."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.platform.application.idempotency import IdempotencyScope
from plm_assistant.modules.plugin.application.package_archive_inspector import MAX_PACKAGE_BYTES


_OPERATION = "V1_PLUGIN_PACKAGE_IMPORT"


class PluginPackageImportQueueError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EnqueuePluginPackageImport:
    scope: IdempotencyScope
    package_upload_id: uuid.UUID
    package_sha256: bytes = field(repr=False)
    package_size_bytes: int
    trace_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.scope) is not IdempotencyScope
                or self.scope.operation != _OPERATION
                or self.scope.project_id is not None
                or type(self.package_upload_id) is not uuid.UUID
                or self.package_upload_id.int == 0
                or type(self.package_sha256) is not bytes
                or len(self.package_sha256) != 32
                or type(self.package_size_bytes) is not int
                or not 0 < self.package_size_bytes <= MAX_PACKAGE_BYTES
                or type(self.trace_id) is not uuid.UUID or self.trace_id.int == 0):
            raise PluginPackageImportQueueError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class PluginPackageImportJobRef:
    job_id: uuid.UUID
    event_id: uuid.UUID
    package_upload_id: uuid.UUID
    package_sha256: bytes = field(repr=False)
    package_size_bytes: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (self.job_id, self.event_id, self.package_upload_id))
                or type(self.package_sha256) is not bytes
                or len(self.package_sha256) != 32
                or type(self.package_size_bytes) is not int
                or not 0 < self.package_size_bytes <= MAX_PACKAGE_BYTES):
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE")


class PluginPackageImportQueueRepositoryPort(Protocol):
    def enqueue_import(
        self, transaction: object, *, request: EnqueuePluginPackageImport,
    ) -> PluginPackageImportJobRef: ...


class PluginPackageImportQueue:
    """Enqueue a bounded verification Job and Outbox pair in the caller UOW."""

    def __init__(self, repository: PluginPackageImportQueueRepositoryPort) -> None:
        if repository is None:
            raise ValueError("Plugin package import queue repository is required")
        self._repository = repository

    def enqueue(self, transaction: object, *,
                request: EnqueuePluginPackageImport) -> PluginPackageImportJobRef:
        if type(request) is not EnqueuePluginPackageImport:
            raise PluginPackageImportQueueError("VALIDATION_FAILED")
        request.__post_init__()
        try:
            result = self._repository.enqueue_import(transaction, request=request)
            if type(result) is not PluginPackageImportJobRef:
                raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE")
            result.__post_init__()
            if (result.package_sha256 != request.package_sha256
                    or result.package_size_bytes != request.package_size_bytes):
                raise PluginPackageImportQueueError("CONFLICT_IDEMPOTENCY")
            return result
        except PluginPackageImportQueueError:
            raise
        except Exception:
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE") from None
