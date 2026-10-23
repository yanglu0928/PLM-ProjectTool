"""Disposable PG read-back of legacy SectionVersion Spec contract after 0178."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_spec_schema_fixture",
    ROOT / "validation/sol-05-a04-p11-p02-section-spec-schema/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def verify(port: int) -> None:
    prior.verify(port)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    with psycopg.connect(**connection) as db:
        version_id, section_id, project_id, series_id, spec_id = db.execute(
            "SELECT v.solution_section_version_id,v.solution_section_id,v.project_id,"
            "s.spec_series_id,s.structured_solution_spec_id "
            "FROM plm.sol_section_versions v JOIN plm.sol_structured_specs s "
            "ON s.project_id=v.project_id ORDER BY v.project_id LIMIT 1").fetchone()
    engine = create_engine(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    repository = SqlAlchemySectionVersionReadRepository()

    def read():
        with Session(engine) as session, session.begin():
            return repository.get(
                SimpleNamespace(session=session), project_id=project_id,
                section_id=section_id, version_id=version_id)

    try:
        old = read()
        assert old is not None
        assert old.spec_binding_state == "UNDECLARED"
        assert old.spec_not_required_reason is None
        assert old.structured_spec_refs == ()
        with psycopg.connect(**connection) as db:
            table = "plm.sol_section_spec_refs"
            db.execute(f"ALTER TABLE {table} DISABLE TRIGGER trg_sol_section_spec_refs__owner")
            try:
                ref_id = db.execute(
                    f"INSERT INTO {table}(solution_section_version_id,"
                    "solution_section_id,project_id,spec_series_id,"
                    "structured_solution_spec_id,ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,1) RETURNING solution_section_spec_ref_id",
                    (version_id, section_id, project_id, series_id, spec_id)).fetchone()[0]
                try:
                    prior.fixture.rejects(
                        "SectionVersion fixed collection is incomplete", read)
                finally:
                    db.execute(f"DELETE FROM {table} "
                               "WHERE solution_section_spec_ref_id=%s", (ref_id,))
            finally:
                db.execute(f"ALTER TABLE {table} ENABLE TRIGGER trg_sol_section_spec_refs__owner")
        assert read() == old
    finally:
        engine.dispose()
    print("SOL_05_A04_P11_P03_SECTION_SPEC_CONTRACT_PASS: legacy PG read-back "
          "UNDECLARED, no implicit waiver and corrupt ref collection fails closed")


if __name__ == "__main__":
    prior.fixture.verify = verify
    prior.fixture.main()
