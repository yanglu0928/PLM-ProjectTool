"""Load and verify the exact Job/staging metadata pair for Plugin import."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.plugin.application.package_import_worker import (
    PluginPackageImportWorkError,
    PluginPackageImportWorkItem,
)
from plm_assistant.modules.plugin.infrastructure.orm import PluginPackageImportStagingRow


class SqlAlchemyPluginPackageImportSource:
    def load(self, transaction: object, *, claim: ClaimedJob) -> PluginPackageImportWorkItem:
        if type(claim) is not ClaimedJob or claim.job_type != "PLUGIN_PACKAGE_VERIFY":
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        session = self._session(transaction)
        job = session.execute(
            select(JobRow).where(JobRow.job_id == claim.job_id)
        ).scalar_one_or_none()
        if (job is None or job.owner_module != "plugin"
                or job.job_type != "PLUGIN_PACKAGE_VERIFY"
                or job.scope != "DEPLOYMENT" or job.project_id is not None
                or job.state != "RUNNING"
                or job.fencing_token != claim.fencing_token
                or job.trace_id != claim.trace_id
                or job.actor_ref is None or not job.actor_ref.int
                or type(job.payload_refs) is not dict
                or set(job.payload_refs) != {
                    "package_upload_id", "sha256", "size_bytes",
                }):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        payload = job.payload_refs
        try:
            upload_id = uuid.UUID(payload["package_upload_id"])
            digest = bytes.fromhex(payload["sha256"])
            size = payload["size_bytes"]
        except (TypeError, ValueError):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE") from None
        if (not upload_id.int or type(payload["sha256"]) is not str
                or payload["sha256"] != digest.hex() or len(digest) != 32
                or type(size) is not int or not 0 < size <= 256 * 1024 * 1024):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        staging = session.execute(
            select(PluginPackageImportStagingRow).where(
                PluginPackageImportStagingRow.package_upload_id == upload_id,
            )
        ).scalar_one_or_none()
        if (staging is None or bytes(staging.package_sha256) != digest
                or staging.package_size_bytes != size
                or len(staging.detached_signature) != 64
                or not staging.signer_key_ref):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        try:
            trace_id = uuid.UUID(job.trace_id)
        except (TypeError, ValueError):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE") from None
        if not trace_id.int or str(trace_id) != job.trace_id:
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        return PluginPackageImportWorkItem(
            package_upload_id=upload_id, actor_id=job.actor_ref, trace_id=trace_id,
            package_sha256=digest, package_size_bytes=size,
            detached_signature=bytes(staging.detached_signature),
            signer_key_ref=staging.signer_key_ref,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginPackageImportWorkError("PLUGIN_PACKAGE_STAGE_UNAVAILABLE")
        return session
