"""Fail-closed Windows Secret write service composition."""

from __future__ import annotations

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.application.secret_write import SecretWriteService
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_write_repository import SqlAlchemySecretWriteRepository
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


SECRET_MASTER_KEY_REF = "secret-master-v1"


class ProductionSecretWriteStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("production secret writes unavailable")


def create_windows_secret_write_service(
    runtime: DatabaseRuntime, *, license_guard: object,
) -> SecretWriteService:
    """Use only the current account's fixed Vault entry, never deployment config."""
    try:
        if not isinstance(runtime, DatabaseRuntime) or license_guard is None:
            raise ProductionSecretWriteStartupError()
        provider = WindowsSecretKeyProvider()
        key = provider.resolve_key(SECRET_MASTER_KEY_REF)
        if type(key) is not bytes or len(key) != 32:
            raise ProductionSecretWriteStartupError()
        return SecretWriteService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyLicenseImportAccess(),
            license_guard=license_guard,
            repository=SqlAlchemySecretWriteRepository(),
            cipher=AesGcmSecretCrypto(provider, key_ref=SECRET_MASTER_KEY_REF),
            audit=AuditService(SqlAlchemyAuditRepository()),
            receipts=SqlAlchemyIdempotencyReceipts(),
        )
    except Exception:
        raise ProductionSecretWriteStartupError() from None
