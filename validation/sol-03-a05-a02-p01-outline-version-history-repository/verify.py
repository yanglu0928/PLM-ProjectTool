"""Disposable Win11 PostgreSQL check of fixed PROJECT/GLOBAL OutlineVersion history."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_http_fixture_history",
    ROOT / "validation/sol-03-a04-p03-p03-p05-a02-outline-version-http-pg/verify.py")
assert SPEC and SPEC.loader
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)


def _ids(port: int, project: uuid.UUID, scope: str):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        return db.execute(
            "SELECT DISTINCT solution_outline_id FROM plm.sol_outline_reference_refs "
            "WHERE project_id=%s AND reference_scope=%s", (project, scope)
        ).fetchall()


def _global_project(port: int) -> uuid.UUID:
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rows = db.execute(
            "SELECT DISTINCT project_id FROM plm.sol_outline_reference_refs "
            "WHERE reference_scope='GLOBAL'").fetchall()
    assert len(rows) == 1, rows
    return rows[0][0]


def _check(*, runtime, project, port, scope, expected):
    rows = _ids(port, project, scope)
    assert len(rows) == 1, rows
    outline = rows[0][0]
    repository = SqlAlchemyOutlineVersionReadRepository()
    with runtime.unit_of_work() as tx:
        items = repository.list(
            tx, project_id=project, outline_id=outline,
            before_version_no=None, limit=expected + 1)
        assert len(items) == expected
        assert tuple(item.version_no for item in items) == tuple(range(expected, 0, -1))
        for item in items:
            assert item.solution_outline_id == outline and item.project_id == project
            assert item.version_state == "DRAFT"
            assert len(item.section_ids) == 1 and len(item.requirement_refs) == 1
            assert len(item.reference_refs) == 1
            assert item.reference_refs[0].scope == scope
            assert repository.get(tx, project_id=project, outline_id=outline,
                                  version_id=item.solution_outline_version_id) == item
            assert repository.get(tx, project_id=uuid.uuid4(), outline_id=outline,
                                  version_id=item.solution_outline_version_id) is None
            assert repository.get(tx, project_id=project, outline_id=uuid.uuid4(),
                                  version_id=item.solution_outline_version_id) is None
        if expected > 1:
            older = repository.list(
                tx, project_id=project, outline_id=outline,
                before_version_no=expected, limit=expected + 1)
            assert older == items[1:]
        assert repository.list(tx, project_id=uuid.uuid4(), outline_id=outline,
                               before_version_no=None, limit=10) == ()
    try:
        with runtime.unit_of_work() as tx:
            repository.list(tx, project_id=project, outline_id=outline,
                            before_version_no=None, limit=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid page limit was accepted")


def project_created(**kwargs):
    previous.project_created(**kwargs)
    _check(runtime=kwargs["runtime"], project=kwargs["project"],
           port=kwargs["port"], scope="PROJECT", expected=2)
    return 0


def global_qualified(**kwargs):
    previous.global_qualified(**kwargs)
    _check(runtime=kwargs["runtime"], project=_global_project(kwargs["port"]),
           port=kwargs["port"], scope="GLOBAL", expected=1)
    return 0


if __name__ == "__main__":
    previous.fixture.main(on_created=project_created)
    previous.composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A05_A02_P01_OUTLINE_HISTORY_REPOSITORY_PG_PASS: "
          "PROJECT/GLOBAL fixed ordered history, page, identity isolation")
