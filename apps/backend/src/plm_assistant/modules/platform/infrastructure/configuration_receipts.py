"""Atomic PostgreSQL replay protection for deployment configuration commands."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.platform.application.configuration_commands import (
    ConfigurationCommandError,
    ConfigurationCommandResult,
)
from plm_assistant.modules.platform.infrastructure.configuration_orm import (
    ConfigurationCommandReceiptRow,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork


class SqlAlchemyConfigurationReceiptRepository:
    def reserve(
        self, uow: SqlAlchemyUnitOfWork, *, actor_id: uuid.UUID,
        operation: str, key_digest: bytes, request_fingerprint: bytes,
    ) -> ConfigurationCommandResult | None:
        inserted = uow.session.execute(
            pg_insert(ConfigurationCommandReceiptRow)
            .values(
                actor_id=actor_id,
                operation=operation,
                key_digest=key_digest,
                request_fingerprint=request_fingerprint,
                state="PENDING",
            )
            .on_conflict_do_nothing(
                index_elements=["actor_id", "operation", "key_digest"]
            )
            .returning(ConfigurationCommandReceiptRow.receipt_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return None
        row = uow.session.execute(
            select(ConfigurationCommandReceiptRow)
            .where(
                ConfigurationCommandReceiptRow.actor_id == actor_id,
                ConfigurationCommandReceiptRow.operation == operation,
                ConfigurationCommandReceiptRow.key_digest == key_digest,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if row is None or row.state != "COMPLETED":
            raise ConfigurationCommandError("SYSTEM_UNAVAILABLE")
        if row.request_fingerprint != request_fingerprint:
            raise ConfigurationCommandError("CONFLICT_IDEMPOTENCY")
        if row.result_configuration_id is None or row.result_lock_version is None:
            raise ConfigurationCommandError("SYSTEM_UNAVAILABLE")
        return ConfigurationCommandResult(
            row.result_configuration_id, row.result_version_id,
            row.result_version_no, row.result_lock_version,
        )

    def complete(
        self, uow: SqlAlchemyUnitOfWork, *, actor_id: uuid.UUID,
        operation: str, key_digest: bytes, result: ConfigurationCommandResult,
    ) -> None:
        changed = uow.session.execute(
            update(ConfigurationCommandReceiptRow)
            .where(
                ConfigurationCommandReceiptRow.actor_id == actor_id,
                ConfigurationCommandReceiptRow.operation == operation,
                ConfigurationCommandReceiptRow.key_digest == key_digest,
                ConfigurationCommandReceiptRow.state == "PENDING",
            )
            .values(
                state="COMPLETED",
                result_configuration_id=result.configuration_id,
                result_version_id=result.version_id,
                result_version_no=result.version_no,
                result_lock_version=result.lock_version,
                completed_at=func.statement_timestamp(),
            )
        )
        if changed.rowcount != 1:
            raise ConfigurationCommandError("SYSTEM_UNAVAILABLE")
