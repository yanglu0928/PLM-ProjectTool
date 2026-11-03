"""Coordinate Plugin package streaming, idempotent jobs, metadata, and audit."""
from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import IdempotencyScope
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork
from plm_assistant.modules.plugin.application.package_archive_inspector import MAX_PACKAGE_BYTES
from plm_assistant.modules.plugin.application.package_import_job_queue import (
    EnqueuePluginPackageImport,
    PluginPackageImportJobRef,
    PluginPackageImportQueue,
    PluginPackageImportQueueError,
)
from plm_assistant.modules.plugin.application.package_import_spool import (
    PluginPackageImportSpool,
    PluginPackageStageError,
)
from plm_assistant.modules.plugin.application.package_import_staging import (
    PluginPackageImportStagingRepositoryPort,
    StorePluginPackageImportStaging,
)


class DeploymentAdminAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class ImportLicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PluginPackageImportError(RuntimeError):
    """Stable, body-free package import failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SubmitPluginPackageImport:
    scope: IdempotencyScope
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    declared_length: int
    declared_sha256: bytes = field(repr=False)
    detached_signature: bytes = field(repr=False)
    signer_key_ref: str = field(repr=False)
    chunks: Iterable[bytes] = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.scope) is not IdempotencyScope
                or type(self.session_token) is not bytes or len(self.session_token) != 32
                or self.scope.operation != "V1_PLUGIN_PACKAGE_IMPORT"
                or self.scope.project_id is not None
                or type(self.trace_id) is not uuid.UUID or self.trace_id.int == 0
                or type(self.declared_length) is not int
                or not 0 < self.declared_length <= MAX_PACKAGE_BYTES
                or type(self.declared_sha256) is not bytes
                or len(self.declared_sha256) != 32
                or type(self.detached_signature) is not bytes
                or len(self.detached_signature) != 64
                or type(self.signer_key_ref) is not str
                or not self.signer_key_ref
                or self.signer_key_ref != self.signer_key_ref.strip()
                or len(self.signer_key_ref.encode("utf-8", "strict")) > 512
                or any(unicodedata.category(c) == "Cc" for c in self.signer_key_ref)
                or not hasattr(self.chunks, "__iter__")):
            raise PluginPackageImportError("VALIDATION_FAILED")


class PluginPackageImportService:
    """Stage signed bytes and atomically enqueue minimized verification evidence."""

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        spool: PluginPackageImportSpool,
        queue: PluginPackageImportQueue,
        staging_repository: PluginPackageImportStagingRepositoryPort,
        admin_access: DeploymentAdminAccessPort,
        license_guard: ImportLicenseGuardPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, spool, queue, staging_repository, admin_access,
            license_guard, audit,
        )):
            raise ValueError("Plugin package import dependencies are required")
        self._uow = unit_of_work
        self._spool = spool
        self._queue = queue
        self._staging = staging_repository
        self._admin_access = admin_access
        self._license_guard = license_guard
        self._audit = audit

    def submit(self, command: SubmitPluginPackageImport) -> PluginPackageImportJobRef:
        if type(command) is not SubmitPluginPackageImport:
            raise PluginPackageImportError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            self._license_guard.require_valid(trace_id=command.trace_id)
            self._require_admin(command)
        except PluginPackageImportError:
            raise
        except Exception:
            raise PluginPackageImportError("LICENSE_OPERATION_DENIED") from None
        package_upload_id = uuid.uuid4()
        try:
            staged = self._spool.receive(
                package_upload_id=package_upload_id,
                chunks=command.chunks,
                declared_length=command.declared_length,
                declared_sha256=command.declared_sha256,
            )
        except PluginPackageStageError as exc:
            raise PluginPackageImportError(exc.code) from None
        try:
            self._license_guard.require_valid(trace_id=command.trace_id)
            with self._uow() as transaction:
                self._require_admin_in_transaction(transaction, command)
                job = self._queue.enqueue(
                    transaction,
                    request=EnqueuePluginPackageImport(
                        scope=command.scope,
                        package_upload_id=staged.package_upload_id,
                        package_sha256=staged.sha256,
                        package_size_bytes=staged.size_bytes,
                        trace_id=command.trace_id,
                    ),
                )
                is_new = job.package_upload_id == staged.package_upload_id
                if is_new:
                    self._staging.add(
                        transaction,
                        request=StorePluginPackageImportStaging(
                            package_upload_id=staged.package_upload_id,
                            package_sha256=staged.sha256,
                            package_size_bytes=staged.size_bytes,
                            detached_signature=command.detached_signature,
                            signer_key_ref=command.signer_key_ref,
                        ),
                    )
                    self._audit.append(
                        transaction,
                        AuditEventDraft(
                            trace_id=command.trace_id,
                            event_scope="DEPLOYMENT",
                            target_project_id=None,
                            actor_type="USER",
                            actor_id=command.scope.actor_id,
                            original_actor_id=None,
                            actor_hint_digest=None,
                            action="PLUGIN_PACKAGE_IMPORT_SUBMIT",
                            outcome="SUCCESS",
                            target_owner_module="plugin",
                            target_object_type="PLG-01",
                            target_object_id=staged.package_upload_id,
                            after_state="PENDING_VERIFICATION",
                        ),
                    )
                transaction.commit()
            if not is_new:
                self._spool.discard(staged)
            return job
        except PluginPackageImportError:
            try:
                self._spool.discard(staged)
            except Exception:
                pass
            raise
        except (PluginPackageImportQueueError, PluginPackageStageError) as exc:
            try:
                self._spool.discard(staged)
            except Exception:
                pass
            raise PluginPackageImportError(exc.code) from None
        except Exception:
            try:
                self._spool.discard(staged)
            except Exception:
                pass
            raise PluginPackageImportError("JOB_STORE_UNAVAILABLE") from None


    def _require_admin(self, command: SubmitPluginPackageImport) -> None:
        with self._uow() as transaction:
            self._require_admin_in_transaction(transaction, command)
            transaction.commit()

    def _require_admin_in_transaction(
        self, transaction: object, command: SubmitPluginPackageImport,
    ) -> None:
        try:
            actor_id = self._admin_access.authorized_admin(
                transaction, session_token=command.session_token,
                now=datetime.now(timezone.utc),
            )
        except Exception:
            raise PluginPackageImportError("AUTH_ACCESS_DENIED") from None
        if actor_id != command.scope.actor_id:
            raise PluginPackageImportError("AUTH_ACCESS_DENIED")
