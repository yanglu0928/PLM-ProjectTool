from __future__ import annotations

import hashlib
import io
import uuid

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.plugin.application.package_import_worker import (
    PluginPackageImportWorker,
    PluginPackageImportWorkItem,
)


class _Transaction:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class _Leases:
    def __init__(self, claim):
        self.claim = claim
        self.finished = []
        self.failures = []
    def claim_next_plugin_package(self, **_):
        return self.claim
    def finish(self, **kwargs):
        self.finished.append(kwargs)
    def retry_or_fail(self, **kwargs):
        self.failures.append(kwargs)
        return "FAILED"


class _LeaseRepository:
    def check_current(self, transaction, **kwargs):
        return _claim()


class _Source:
    def __init__(self, item): self.item = item
    def load(self, transaction, *, claim): return self.item


class _Storage:
    def __init__(self, body): self.body = body
    @staticmethod
    def locators(**kwargs): return "temp/global/objects/00/00000000000000000000000000000000", "global/objects/00/00000000000000000000000000000000"
    def open_private_staging_snapshot(self, locator, **kwargs): return io.BytesIO(self.body)


class _Registration:
    def __init__(self, package):
        self.package = package
        self.commands = []
    def register(self, command, *, commit_guard):
        commit_guard(_Transaction())
        self.commands.append(command)
        return self.package


class _ArchiveStore:
    def __init__(self, events): self.events = events
    def store_plugin_package_archive(self, **kwargs): self.events.append(kwargs)


class _License:
    def require_valid(self, *, trace_id): return object()


def _claim():
    return ClaimedJob(
        job_id=uuid.UUID(int=1), job_type="PLUGIN_PACKAGE_VERIFY",
        scope="DEPLOYMENT", project_id=None,
        payload_refs={}, trace_id=str(uuid.UUID(int=4)),
        fencing_token=1, attempt_no=1,
    )


def _build(body=b"bounded synthetic archive"):
    digest = hashlib.sha256(body).digest()
    claim = _claim()
    upload_id = uuid.UUID(int=2)
    claim = ClaimedJob(
        claim.job_id, claim.job_type, claim.scope, claim.project_id,
        {"package_upload_id": str(upload_id), "sha256": digest.hex(),
         "size_bytes": len(body)}, claim.trace_id, claim.fencing_token,
        claim.attempt_no,
    )
    item = PluginPackageImportWorkItem(
        package_upload_id=upload_id, actor_id=uuid.UUID(int=3),
        trace_id=uuid.UUID(int=4), package_sha256=digest,
        package_size_bytes=len(body), detached_signature=b"s" * 64,
        signer_key_ref="test-key:fixture",
    )
    leases = _Leases(claim)
    package_id = uuid.UUID(int=5)
    from plm_assistant.modules.plugin.application.package_registration import PluginPackageIdentity
    registration = _Registration(PluginPackageIdentity(
        plugin_package_id=package_id, plugin_id_normalized="fixture.plugin",
        plugin_version="1.0.0", package_sha256=digest, signature=b"s" * 64,
        signer_key_ref="test-key:fixture", compatibility_policy_ref="host.platforms.v1",
        manifest_snapshot={"schema_version": "plm.plugin.manifest.v1"},
        package_state="VERIFIED",
    ))
    archive_events = []
    worker = PluginPackageImportWorker(
        unit_of_work=_Transaction, leases=leases,
        lease_repository=_LeaseRepository(), source=_Source(item),
        storage=_Storage(body), archive_store=_ArchiveStore(archive_events),
        registration=registration, license_guard=_License(),
        worker_ref="plugin-test", lease_seconds=30,
    )
    return worker, leases, registration, archive_events


def test_worker_verifies_payload_and_finishes_only_after_registration():
    worker, leases, registration, archive_events = _build()
    assert worker.run_once() == "SUCCEEDED"
    assert len(registration.commands) == 1
    assert registration.commands[0].compatibility_policy_ref == "host.platforms.v1"
    assert len(archive_events) == 1
    assert archive_events[0]["package_id"] == uuid.UUID(int=5)
    assert archive_events[0]["expected_size"] == len(b"bounded synthetic archive")
    assert len(leases.finished) == 1
    assert leases.failures == []


def test_worker_marks_mismatched_staged_body_retryable_without_registration():
    worker, leases, registration, archive_events = _build(body=b"tampered archive")
    # The fake source reports a different metadata digest than the bytes on storage.
    old = worker._source.item
    worker._source.item = PluginPackageImportWorkItem(
        old.package_upload_id, old.actor_id, old.trace_id,
        hashlib.sha256(b"expected").digest(), old.package_size_bytes,
        old.detached_signature, old.signer_key_ref,
    )
    assert worker.run_once() == "FAILED"
    assert registration.commands == []
    assert archive_events == []
    assert leases.finished == []
    assert leases.failures[0]["error_code"] == "PLUGIN_PACKAGE_STAGE_UNAVAILABLE"


class _UnavailableArchiveStore:
    def store_plugin_package_archive(self, **kwargs):
        raise OSError("synthetic storage failure")


def test_worker_retries_archive_storage_failure_without_finishing_job():
    worker, leases, registration, _archive_events = _build()
    worker._archive_store = _UnavailableArchiveStore()
    assert worker.run_once() == "FAILED"
    assert len(registration.commands) == 1
    assert leases.finished == []
    assert leases.failures[0]["error_code"] == "PLUGIN_PACKAGE_ARCHIVE_STORE_UNAVAILABLE"
    assert leases.failures[0]["retryable"] is True
