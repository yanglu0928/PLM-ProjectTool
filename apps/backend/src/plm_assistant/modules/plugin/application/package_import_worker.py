"""Fenced Plugin package verification worker; never installs or executes archives."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from typing import BinaryIO, Callable, Protocol

from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService,
)
from plm_assistant.modules.plugin.application.package_archive_inspector import MAX_PACKAGE_BYTES
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageRegistrationError,
    PluginPackageRegistrationService,
    RegisterPluginPackageCommand,
)


class PluginPackageImportWorkError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginPackageImportWorkItem:
    package_upload_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    package_sha256: bytes = field(repr=False)
    package_size_bytes: int
    detached_signature: bytes = field(repr=False)
    signer_key_ref: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.package_upload_id) is not uuid.UUID or not self.package_upload_id.int
                or type(self.actor_id) is not uuid.UUID or not self.actor_id.int
                or type(self.trace_id) is not uuid.UUID or not self.trace_id.int
                or type(self.package_sha256) is not bytes or len(self.package_sha256) != 32
                or type(self.package_size_bytes) is not int
                or not 0 < self.package_size_bytes <= MAX_PACKAGE_BYTES
                or type(self.detached_signature) is not bytes
                or len(self.detached_signature) != 64
                or type(self.signer_key_ref) is not str or not self.signer_key_ref):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")


class PluginPackageImportSourcePort(Protocol):
    def load(self, transaction: object, *, claim: ClaimedJob) -> PluginPackageImportWorkItem: ...


class PluginPackageImportStoragePort(Protocol):
    @staticmethod
    def locators(*, scope: str, project_id: uuid.UUID | None,
                 file_object_id: uuid.UUID) -> tuple[str, str]: ...

    def open_private_staging_snapshot(self, locator: str, *, expected_sha256: bytes,
                                      expected_size: int, max_bytes: int) -> BinaryIO: ...


class PluginPackageImportLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PluginPackageImportLeaseRepositoryPort(Protocol):
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class PluginPackageImportWorker:
    """Processes one Owner-scoped leased Job and commits only verified metadata."""

    _policy_ref = "host.platforms.v1"

    def __init__(self, *, unit_of_work: Callable[[], object],
                 leases: JobLeaseService,
                 lease_repository: PluginPackageImportLeaseRepositoryPort,
                 source: PluginPackageImportSourcePort,
                 storage: PluginPackageImportStoragePort,
                 registration: PluginPackageRegistrationService,
                 license_guard: PluginPackageImportLicensePort,
                 worker_ref: str,
                 lease_seconds: int = 3600) -> None:
        if any(value is None for value in (
            unit_of_work, leases, lease_repository, source, storage,
            registration, license_guard,
        )) or type(worker_ref) is not str or not worker_ref:
            raise ValueError("Explicit Plugin package worker dependencies required")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Bounded Plugin package lease required")
        self._uow = unit_of_work
        self._leases = leases
        self._lease_repository = lease_repository
        self._source = source
        self._storage = storage
        self._registration = registration
        self._license_guard = license_guard
        self._worker_ref = worker_ref
        self._lease_seconds = lease_seconds

    def run_once(self) -> str:
        claim = self._leases.claim_next_plugin_package(
            worker_ref=self._worker_ref, lease_seconds=self._lease_seconds,
        )
        if claim is None:
            return "IDLE"
        if (type(claim) is not ClaimedJob or claim.job_type != "PLUGIN_PACKAGE_VERIFY"
                or claim.scope != "DEPLOYMENT" or claim.project_id is not None
                or type(claim.payload_refs) is not dict
                or type(claim.trace_id) is not str):
            raise JobLeaseError("INCONSISTENT_LEASE")
        try:
            with self._uow() as transaction:
                item = self._source.load(transaction, claim=claim)
            if type(item) is not PluginPackageImportWorkItem:
                raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
            item.__post_init__()
            payload = claim.payload_refs
            if (set(payload) != {"package_upload_id", "sha256", "size_bytes"}
                    or payload.get("package_upload_id") != str(item.package_upload_id)
                    or payload.get("sha256") != item.package_sha256.hex()
                    or payload.get("size_bytes") != item.package_size_bytes
                    or claim.trace_id != str(item.trace_id)):
                raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
            staging_locator, _ = self._storage.locators(
                scope="GLOBAL", project_id=None,
                file_object_id=item.package_upload_id,
            )
            with self._storage.open_private_staging_snapshot(
                staging_locator, expected_sha256=item.package_sha256,
                expected_size=item.package_size_bytes, max_bytes=MAX_PACKAGE_BYTES,
            ) as stream:
                archive_bytes = stream.read(item.package_size_bytes + 1)
            if (type(archive_bytes) is not bytes
                    or len(archive_bytes) != item.package_size_bytes
                    or not hmac.compare_digest(
                        hashlib.sha256(archive_bytes).digest(), item.package_sha256,
                    )):
                raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
            self._license_guard.require_valid(trace_id=item.trace_id)

            def commit_guard(transaction: object) -> None:
                current = self._lease_repository.check_current(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token, worker_ref=self._worker_ref,
                )
                if (type(current) is not ClaimedJob
                        or current.job_id != claim.job_id
                        or current.fencing_token != claim.fencing_token
                        or current.job_type != "PLUGIN_PACKAGE_VERIFY"):
                    raise JobLeaseError("STALE_LEASE")

            self._registration.register(
                RegisterPluginPackageCommand(
                    archive_bytes=archive_bytes,
                    detached_signature=item.detached_signature,
                    signer_key_ref=item.signer_key_ref,
                    compatibility_policy_ref=self._policy_ref,
                    trace_id=item.trace_id,
                    actor_id=item.actor_id,
                ),
                commit_guard=commit_guard,
            )
            self._leases.finish(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref=self._worker_ref, publish=lambda _tx, _claim: None,
            )
            return "SUCCEEDED"
        except PluginPackageRegistrationError as exc:
            retryable = exc.code in {
                "PLUGIN_PACKAGE_STORE_UNAVAILABLE",
                "PLUGIN_PACKAGE_POLICY_UNAVAILABLE",
            }
            state = self._fail(claim, exc.code, retryable=retryable)
            return state
        except PluginPackageImportWorkError as exc:
            state = self._fail(
                claim, exc.code,
                retryable=exc.code == "PLUGIN_PACKAGE_STAGE_UNAVAILABLE",
            )
            return state
        except JobLeaseError:
            raise
        except Exception:
            state = self._fail(
                claim, "PLUGIN_PACKAGE_WORKER_UNAVAILABLE", retryable=True,
            )
            return state

    def _fail(self, claim: ClaimedJob, code: str, *, retryable: bool) -> str:
        delay = {1: 5, 2: 15}.get(claim.attempt_no, 0)
        return self._leases.retry_or_fail(
            job_id=claim.job_id, fencing_token=claim.fencing_token,
            worker_ref=self._worker_ref, error_code=code,
            retryable=retryable, delay_seconds=delay,
        )
