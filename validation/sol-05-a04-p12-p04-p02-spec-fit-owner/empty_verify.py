"""Disposable PG18 empty 0182 upgrade/down/re-up and ORM drift proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "fit_owner_empty_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "20261023_0181")
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "20261023_0181")
    print("SOL_05_A04_P12_P04_P02_EMPTY_MIGRATION_PASS: 0182 empty "
          "upgrade/down/re-up and head ORM drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
