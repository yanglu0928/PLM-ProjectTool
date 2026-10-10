from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import (
    validate_database_url,
)


MIGRATION_PACKAGE = Path(__file__).resolve().parents[3] / "migrations"


def create_migration_config(database_url: str | URL) -> Config:
    """Create an in-memory Alembic config without persisting credentials."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATION_PACKAGE))
    config.attributes["database_url"] = validate_database_url(database_url)
    config.attributes["configure_logger"] = False
    return config


def upgrade_database(database_url: str | URL, revision: str = "head") -> None:
    command.upgrade(create_migration_config(database_url), revision)


def downgrade_database(database_url: str | URL, revision: str = "base") -> None:
    command.downgrade(create_migration_config(database_url), revision)
