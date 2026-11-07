from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from plm_assistant.modules.platform.application.idempotency import IdempotencyScope
from plm_assistant.modules.plugin.application.package_import_job_queue import (
    PluginPackageImportJobRef,
    PluginPackageImportQueue,
)
from plm_assistant.modules.plugin.application.package_import_service import (
    PluginPackageImportError,
    PluginPackageImportService,
    SubmitPluginPackageImport,
)
from plm_assistant.modules.plugin.application.package_import_spool import (
    PluginPackageImportSpool,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage,
    LocalStorageError,
)


class TrackingStorage(LocalFileStorage):
    def __init__(self, root):
        super().__init__(root)
        self.locators_written = []

    def reserve_staging(self, locator):
        self.locators_written.append(locator)
        return super().reserve_staging(locator)


class QueueRepository:
    def __init__(self, replay=None):
        self.replay = replay
        self.request = None

    def enqueue_import(self, transaction, *, request):
        self.request = request
        if self.replay is not None:
            return self.replay
        return PluginPackageImportJobRef(
            uuid.uuid4(), uuid.uuid4(), request.package_upload_id,
            request.package_sha256, request.package_size_bytes,
        )


class AdminAccess:
    def __init__(self, actor_id):
        self.actor_id = actor_id
        self.checks = 0

    def authorized_admin(self, transaction, *, session_token, now):
        self.checks += 1
        assert len(session_token) == 32
        assert now.tzinfo is not None
        return self.actor_id


class LicenseGuard:
    def __init__(self):
        self.checks = []

    def require_valid(self, *, trace_id):
        self.checks.append(trace_id)
        return object()


class StagingRepository:
    def __init__(self):
        self.requests = []

    def add(self, transaction, *, request):
        self.requests.append(request)


class Audit:
    def __init__(self):
        self.events = []

    def append(self, transaction, draft):
        self.events.append(draft)


class UnitOfWork:
    def __init__(self, *, fail_commit=False):
        self.fail_commit = fail_commit
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or not self.committed:
            self.rolled_back = True
        return False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("database failure")
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _scope():
    return IdempotencyScope.from_key(
        actor_id=uuid.UUID(int=1), project_id=None,
        operation="V1_PLUGIN_PACKAGE_IMPORT",
        key="stable-plugin-import-key",
    )


def _command(payload=b"PK\\x03\\x04 synthetic plugin", scope=None):
    return SubmitPluginPackageImport(
        scope=scope or _scope(), session_token=b"t" * 32, trace_id=uuid.uuid4(),
        declared_length=len(payload), declared_sha256=hashlib.sha256(payload).digest(),
        detached_signature=b"s" * 64, signer_key_ref="test-key:fixture",
        chunks=(payload[:3], payload[3:]),
    )


def _service(tmp_path, *, replay=None, fail_commit=False):
    storage = TrackingStorage(tmp_path)
    uow = UnitOfWork(fail_commit=fail_commit)
    queue_repository = QueueRepository(replay=replay)
    staging = StagingRepository()
    audit = Audit()
    admin = AdminAccess(uuid.UUID(int=1))
    license_guard = LicenseGuard()
    service = PluginPackageImportService(
        unit_of_work=lambda: uow,
        spool=PluginPackageImportSpool(storage=storage, max_bytes=1024),
        queue=PluginPackageImportQueue(queue_repository),
        staging_repository=staging,
        admin_access=admin,
        license_guard=license_guard,
        audit=audit,
    )
    return service, storage, uow, queue_repository, staging, audit, admin, license_guard


def test_submit_persists_signature_metadata_job_and_audit_in_one_uow(tmp_path):
    service, storage, uow, queue, staging, audit, admin, guard = _service(tmp_path)
    command = _command()

    result = service.submit(command)

    assert uow.committed is True
    assert uow.rolled_back is False
    assert result.package_upload_id == queue.request.package_upload_id
    assert len(staging.requests) == 1
    stored = staging.requests[0]
    assert stored.package_upload_id == result.package_upload_id
    assert stored.package_sha256 == command.declared_sha256
    assert stored.package_size_bytes == command.declared_length
    assert stored.detached_signature == command.detached_signature
    assert stored.signer_key_ref == command.signer_key_ref
    assert len(audit.events) == 1
    assert audit.events[0].action == "PLUGIN_PACKAGE_IMPORT_SUBMIT"
    assert queue.request.package_upload_id == result.package_upload_id
    assert queue.request.package_sha256 == command.declared_sha256
    assert storage.locators_written
    assert admin.checks == 2
    assert len(guard.checks) == 2


def test_idempotent_replay_discards_duplicate_file_without_duplicate_metadata_or_audit(tmp_path):
    prior = PluginPackageImportJobRef(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), hashlib.sha256(
            b"PK\\x03\\x04 synthetic plugin"
        ).digest(), len(b"PK\\x03\\x04 synthetic plugin"),
    )
    service, storage, uow, queue, staging, audit, admin, guard = _service(tmp_path, replay=prior)

    result = service.submit(_command())

    assert result == prior
    assert uow.committed is True
    assert staging.requests == []
    assert audit.events == []
    locator = storage.locators_written[0]
    with pytest.raises(LocalStorageError):
        storage.verify_content(
            locator, expected_sha256=prior.package_sha256,
            expected_size=prior.package_size_bytes, max_bytes=1024,
        )


def test_database_commit_failure_removes_only_new_staged_file(tmp_path):
    service, storage, uow, queue, staging, audit, admin, guard = _service(
        tmp_path, fail_commit=True,
    )

    with pytest.raises(PluginPackageImportError) as caught:
        service.submit(_command())

    assert caught.value.code == "JOB_STORE_UNAVAILABLE"
    assert uow.rolled_back is True
    assert staging.requests
    assert audit.events
    locator = storage.locators_written[0]
    with pytest.raises(LocalStorageError):
        storage.verify_content(
            locator, expected_sha256=queue.request.package_sha256,
            expected_size=queue.request.package_size_bytes, max_bytes=1024,
        )
