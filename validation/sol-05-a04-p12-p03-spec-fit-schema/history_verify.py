"""PG18 existing approved Section Spec refs across nullable 0181 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "fixed_spec_owner_for_fit_schema",
    ROOT / "validation/sol-05-a04-p11-p04-p02-a02-fixed-spec-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
fixture = prior.prior
_owner = prior._after_submit


def _after_submit(*, port, **context):
    _owner(port=port, **context)
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres")
    with psycopg.connect(**connection) as database:
        rows = database.execute(
            "SELECT solution_section_spec_ref_id,fit_rationale "
            "FROM plm.sol_section_spec_refs").fetchall()
        assert len(rows) == 1 and rows[0][1] is None
        ref_id = rows[0][0]
        try:
            database.execute(
                "INSERT INTO plm.sol_section_spec_refs "
                "(solution_section_version_id,solution_section_id,project_id,"
                "spec_series_id,structured_solution_spec_id,ordinal,fit_rationale) "
                "SELECT solution_section_version_id,solution_section_id,project_id,"
                "spec_series_id,structured_solution_spec_id,2,'Human fit basis' "
                "FROM plm.sol_section_spec_refs WHERE solution_section_spec_ref_id=%s",
                (ref_id,))
        except psycopg.Error as error:
            assert "fit Owner is not installed" in str(error)
            database.rollback()
        else:
            raise AssertionError("new fit values must remain write-closed")
    command.downgrade(cfg, "20261023_0180")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as database:
        assert database.execute(
            "SELECT fit_rationale FROM plm.sol_section_spec_refs "
            "WHERE solution_section_spec_ref_id=%s", (ref_id,)).fetchone() == (None,)
        for invalid in (" ", "x" * 1001):
            try:
                database.execute("SET LOCAL session_replication_role='replica'")
                database.execute(
                    "UPDATE plm.sol_section_spec_refs SET fit_rationale=%s "
                    "WHERE solution_section_spec_ref_id=%s", (invalid, ref_id))
            except psycopg.Error as error:
                assert "ck_sol_section_specs__fit_rationale" in str(error)
                database.rollback()
            else:
                raise AssertionError("invalid fit rationale must violate constraint")
        database.execute("SET LOCAL session_replication_role='replica'")
        database.execute(
            "UPDATE plm.sol_section_spec_refs SET fit_rationale='Human fit basis' "
            "WHERE solution_section_spec_ref_id=%s", (ref_id,))
        database.commit()
    try:
        command.downgrade(cfg, "20261023_0180")
    except RuntimeError as error:
        assert "Section Spec fit history prevents downgrade" in str(error)
    else:
        raise AssertionError("non-null fit history must refuse downgrade")
    print("SOL_05_A04_P12_P03_HISTORY_SCHEMA_PASS: existing fixed SpecRef NULL "
          "preserved across 0180/0181, new fit write closed, invalid lengths denied, "
          "non-null history prevents downgrade and head drift clear")


if __name__ == "__main__":
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
