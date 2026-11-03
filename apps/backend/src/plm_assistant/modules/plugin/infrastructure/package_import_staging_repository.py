"""SQLAlchemy owner for append-only Plugin import staging metadata."""
from __future__ import annotations

from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.package_import_staging import (
    PluginPackageImportStagingRepositoryPort,
    StorePluginPackageImportStaging,
)
from plm_assistant.modules.plugin.infrastructure.orm import PluginPackageImportStagingRow


class SqlAlchemyPluginPackageImportStagingRepository(PluginPackageImportStagingRepositoryPort):
    """Add staging metadata to the caller's transaction; never commits it."""

    def add(self, transaction: object, *, request: StorePluginPackageImportStaging) -> None:
        if type(request) is not StorePluginPackageImportStaging:
            raise ValueError("Invalid Plugin package import staging request")
        request.__post_init__()
        session = self._session(transaction)
        session.add(PluginPackageImportStagingRow(
            package_upload_id=request.package_upload_id,
            package_sha256=request.package_sha256,
            package_size_bytes=request.package_size_bytes,
            detached_signature=request.detached_signature,
            signer_key_ref=request.signer_key_ref,
        ))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise RuntimeError("Plugin package import transaction unavailable") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("Plugin package import transaction unavailable")
        return session
