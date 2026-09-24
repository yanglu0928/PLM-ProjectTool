"""PostgreSQL repository for PLT-01 version commands only."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.platform.application.configuration_commands import (
    ConfigurationSnapshot,
    ConfigurationVersionSnapshot,
)
from plm_assistant.modules.platform.infrastructure.configuration_orm import (
    ConfigurationVersionRow,
    SystemConfigurationRow,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork


class SqlAlchemyConfigurationRepository:
    def add_configuration(
        self, uow: SqlAlchemyUnitOfWork, *, configuration_id: uuid.UUID,
        config_key: str, actor_id: uuid.UUID,
    ) -> bool:
        inserted = uow.session.execute(
            pg_insert(SystemConfigurationRow)
            .values(
                system_configuration_id=configuration_id,
                config_key=config_key,
                state="INACTIVE",
                created_by=actor_id,
                updated_by=actor_id,
            )
            .on_conflict_do_nothing(index_elements=["config_key"])
            .returning(SystemConfigurationRow.system_configuration_id)
        ).scalar_one_or_none()
        return inserted is not None

    def lock(
        self, uow: SqlAlchemyUnitOfWork, configuration_id: uuid.UUID
    ) -> ConfigurationSnapshot | None:
        row = uow.session.execute(
            select(SystemConfigurationRow)
            .where(SystemConfigurationRow.system_configuration_id == configuration_id)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return ConfigurationSnapshot(
            row.system_configuration_id, row.config_key,
            row.lock_version, row.active_version_id,
        )

    def latest(
        self, uow: SqlAlchemyUnitOfWork, configuration_id: uuid.UUID
    ) -> ConfigurationVersionSnapshot | None:
        row = uow.session.execute(
            select(ConfigurationVersionRow)
            .where(ConfigurationVersionRow.system_configuration_id == configuration_id)
            .order_by(ConfigurationVersionRow.version_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        return None if row is None else ConfigurationVersionSnapshot(
            row.configuration_version_id, row.version_no
        )

    def get_version(
        self, uow: SqlAlchemyUnitOfWork, configuration_id: uuid.UUID,
        version_no: int,
    ) -> ConfigurationVersionSnapshot | None:
        row = uow.session.execute(
            select(ConfigurationVersionRow).where(
                ConfigurationVersionRow.system_configuration_id == configuration_id,
                ConfigurationVersionRow.version_no == version_no,
            )
        ).scalar_one_or_none()
        return None if row is None else ConfigurationVersionSnapshot(
            row.configuration_version_id, row.version_no
        )

    def add_version(
        self, uow: SqlAlchemyUnitOfWork, *, configuration_id: uuid.UUID,
        version_id: uuid.UUID, version_no: int,
        supersedes_version_id: uuid.UUID | None, schema_version: int,
        value_type: str, value: Any, fingerprint: bytes, actor_id: uuid.UUID,
    ) -> None:
        uow.session.add(ConfigurationVersionRow(
            configuration_version_id=version_id,
            system_configuration_id=configuration_id,
            version_no=version_no,
            version_state="ACTIVE",  # availability, not the root's active pointer
            supersedes_version_id=supersedes_version_id,
            schema_version=schema_version,
            value_type=value_type,
            value_json=value,
            content_fingerprint=fingerprint,
            created_by=actor_id,
        ))
        uow.session.flush()

    def update_root(
        self, uow: SqlAlchemyUnitOfWork, *, configuration_id: uuid.UUID,
        expected_lock_version: int, actor_id: uuid.UUID,
        active_version_id: uuid.UUID | None = None,
    ) -> bool:
        values: dict[str, Any] = {
            "lock_version": SystemConfigurationRow.lock_version + 1,
            "updated_at": func.statement_timestamp(),
            "updated_by": actor_id,
        }
        if active_version_id is not None:
            values["active_version_id"] = active_version_id
            values["state"] = "ACTIVE"
        result = uow.session.execute(
            update(SystemConfigurationRow)
            .where(
                SystemConfigurationRow.system_configuration_id == configuration_id,
                SystemConfigurationRow.lock_version == expected_lock_version,
            )
            .values(**values)
        )
        return result.rowcount == 1
