"""PLT-01 deployment configuration persistence; values must be non-sensitive."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class SystemConfigurationRow(Base):
    __tablename__ = "plt_system_configurations"
    __table_args__ = (
        UniqueConstraint("config_key"),
        CheckConstraint("config_key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$' AND char_length(config_key) <= 64", name="ck_plt_system_configurations__config_key_format"),
        CheckConstraint("state IN ('ACTIVE', 'INACTIVE')", name="ck_plt_system_configurations__state"),
        CheckConstraint("lock_version >= 0", name="ck_plt_system_configurations__lock_version"),
        ForeignKeyConstraint(
            ["active_version_id", "system_configuration_id"],
            ["plm.plt_configuration_versions.configuration_version_id", "plm.plt_configuration_versions.system_configuration_id"],
            name="fk_plt_cfg__active_version",
            ondelete="NO ACTION",
            use_alter=True,
        ),
    )

    system_configuration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    config_key: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INACTIVE'"))
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retention_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class ConfigurationVersionRow(Base):
    __tablename__ = "plt_configuration_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["system_configuration_id"],
            ["plm.plt_system_configurations.system_configuration_id"],
            name="fk_plt_cfg_ver__config",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_id", "system_configuration_id"],
            ["plm.plt_configuration_versions.configuration_version_id", "plm.plt_configuration_versions.system_configuration_id"],
            name="fk_plt_cfg_ver__supersedes",
            ondelete="NO ACTION",
        ),
        UniqueConstraint("system_configuration_id", "version_no"),
        UniqueConstraint("configuration_version_id", "system_configuration_id"),
        CheckConstraint("version_no > 0", name="ck_plt_configuration_versions__version_no"),
        CheckConstraint("version_state IN ('ACTIVE', 'INACTIVE')", name="ck_plt_configuration_versions__version_state"),
        CheckConstraint("value_type IN ('STRING', 'INTEGER', 'BOOLEAN', 'JSON')", name="ck_plt_configuration_versions__value_type"),
        CheckConstraint("octet_length(content_fingerprint) = 32", name="ck_plt_configuration_versions__content_fingerprint"),
        CheckConstraint("(value_type = 'STRING' AND jsonb_typeof(value_json) = 'string') OR (value_type = 'INTEGER' AND jsonb_typeof(value_json) = 'number') OR (value_type = 'BOOLEAN' AND jsonb_typeof(value_json) = 'boolean') OR (value_type = 'JSON' AND jsonb_typeof(value_json) IN ('object', 'array'))", name="ck_plt_configuration_versions__value_shape"),
    )

    configuration_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    system_configuration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    value_type: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
