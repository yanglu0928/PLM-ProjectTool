"""Job-owned Plugin import Job/Outbox persistence; caller owns the transaction."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow
from plm_assistant.modules.plugin.application.package_import_job_queue import (
    EnqueuePluginPackageImport,
    PluginPackageImportJobRef,
    PluginPackageImportQueueError,
)


_OWNER = "plugin"
_JOB_TYPE = "PLUGIN_PACKAGE_VERIFY"
_EVENT_TYPE = "PLUGIN_PACKAGE_IMPORT_REQUESTED"
_SCOPE = "DEPLOYMENT"


def _key(request: EnqueuePluginPackageImport) -> str:
    digest = hashlib.sha256(
        b"PLM-PLUGIN-PACKAGE-IMPORT-V1\\x00"
        + request.scope.actor_id.bytes
        + request.scope.operation.encode("ascii")
        + request.scope.key_digest
    ).hexdigest()
    return digest


class SqlAlchemyPluginPackageImportQueueRepository:
    def enqueue_import(
        self, transaction: object, *, request: EnqueuePluginPackageImport,
    ) -> PluginPackageImportJobRef:
        if type(request) is not EnqueuePluginPackageImport:
            raise PluginPackageImportQueueError("VALIDATION_FAILED")
        request.__post_init__()
        session = self._session(transaction)
        connection = session.connection()
        if (connection.dialect.name != "postgresql"
                or connection.get_isolation_level() != "READ COMMITTED"):
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE")
        key = _key(request)
        try:
            session.execute(
                select(func.pg_advisory_xact_lock(
                    func.hashtextextended("plugin-package-import:" + key, 0)
                ))
            )
            job = session.execute(
                select(JobRow).where(
                    JobRow.owner_module == _OWNER,
                    JobRow.scope == _SCOPE,
                    JobRow.project_id.is_(None),
                    JobRow.job_type == _JOB_TYPE,
                    JobRow.idempotency_key == key,
                ).with_for_update(of=JobRow)
            ).scalar_one_or_none()
            event = session.execute(
                select(OutboxEventRow).where(
                    OutboxEventRow.owner_module == _OWNER,
                    OutboxEventRow.scope == _SCOPE,
                    OutboxEventRow.project_id.is_(None),
                    OutboxEventRow.event_type == _EVENT_TYPE,
                    OutboxEventRow.idempotency_key == key,
                ).with_for_update(of=OutboxEventRow)
            ).scalar_one_or_none()

            if job is not None or event is not None:
                return self._replay(request, key, job, event)

            job_id, event_id = session.execute(
                select(func.uuidv7(), func.uuidv7())
            ).one()
            upload_id = request.package_upload_id
            payload = {
                "package_upload_id": str(upload_id),
                "sha256": request.package_sha256.hex(),
                "size_bytes": request.package_size_bytes,
            }
            session.add(JobRow(
                job_id=job_id, owner_module=_OWNER, job_type=_JOB_TYPE,
                scope=_SCOPE, project_id=None,
                actor_ref=request.scope.actor_id, trace_id=str(request.trace_id),
                payload_refs=payload, idempotency_key=key, max_attempts=3,
            ))
            session.add(OutboxEventRow(
                event_id=event_id, event_type=_EVENT_TYPE, owner_module=_OWNER,
                scope=_SCOPE, project_id=None, aggregate_ref=upload_id,
                aggregate_version=1,
                payload_refs={"job_id": str(job_id),
                              "package_upload_id": str(upload_id)},
                idempotency_key=key, trace_id=str(request.trace_id),
                max_attempts=5,
            ))
            session.flush()
            return PluginPackageImportJobRef(
                job_id, event_id, upload_id,
                request.package_sha256, request.package_size_bytes,
            )
        except PluginPackageImportQueueError:
            raise
        except Exception:
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE") from None

    @staticmethod
    def _replay(request, key, job, event) -> PluginPackageImportJobRef:
        if job is None or event is None:
            raise PluginPackageImportQueueError("CONFLICT_STATE")
        payload = job.payload_refs
        if type(payload) is not dict or set(payload) != {
            "package_upload_id", "sha256", "size_bytes",
        }:
            raise PluginPackageImportQueueError("CONFLICT_STATE")
        try:
            from uuid import UUID
            upload_id = UUID(payload["package_upload_id"])
            digest = bytes.fromhex(payload["sha256"])
            size = payload["size_bytes"]
        except (TypeError, ValueError):
            raise PluginPackageImportQueueError("CONFLICT_STATE") from None
        if (not upload_id.int or digest != request.package_sha256
                or size != request.package_size_bytes
                or job.actor_ref != request.scope.actor_id
                or job.max_attempts != 3
                or job.trace_id != event.trace_id
                or event.idempotency_key != key
                or event.aggregate_ref != upload_id
                or event.aggregate_version != 1
                or event.payload_refs != {
                    "job_id": str(job.job_id),
                    "package_upload_id": str(upload_id),
                }
                or event.max_attempts != 5):
            raise PluginPackageImportQueueError("CONFLICT_IDEMPOTENCY")
        return PluginPackageImportJobRef(
            job.job_id, event.event_id, upload_id, digest, size,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginPackageImportQueueError("JOB_STORE_UNAVAILABLE")
        return session
