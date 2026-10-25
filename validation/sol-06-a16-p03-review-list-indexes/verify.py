"""Verify REVIEW_LIST indexes on a disposable Windows PostgreSQL 18.6 cluster."""

from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


PORT = 55432
PREFIX = "plm-review-list-indexes-"
PREVIOUS = "20261019_0165"
HEAD = "20261019_0166"
REVIEW_INDEX = "ix_rvw_reviews__scope_created"
ASSIGNMENT_INDEX = "ix_rvw_assignments__reviewer_pending"


def _fixture(repo: Path):
    path = repo / "validation" / "rvw-01-a02-review-schema" / "verify.py"
    spec = spec_from_file_location("_review_list_index_fixture", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _command(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        output = (result.stdout + result.stderr)[-2000:]
        raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}: {output}")
    return result.stdout.strip()


def _port_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError:
            return False
        return True


def _safe_run_dir(run: Path, root: Path) -> bool:
    resolved_root = root.resolve(strict=True)
    resolved_run = run.resolve(strict=True)
    return (
        resolved_run.parent == resolved_root
        and resolved_run.name.startswith(PREFIX)
        and resolved_run != resolved_root
        and resolved_run.is_dir()
    )


def _url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username="poc_admin",
        host="127.0.0.1",
        port=PORT,
        database=database,
    )


def _connect(database: str):
    return psycopg.connect(
        host="127.0.0.1",
        port=PORT,
        user="poc_admin",
        dbname=database,
        autocommit=True,
    )


def _version(connection) -> str:
    return connection.execute(
        "SELECT version_num FROM plm.alembic_version"
    ).fetchone()[0]


def _index_definitions(connection) -> dict[str, str]:
    return dict(
        connection.execute(
            """
            SELECT indexname,indexdef
              FROM pg_indexes
             WHERE schemaname='plm'
               AND indexname IN (%s,%s)
             ORDER BY indexname
            """,
            (REVIEW_INDEX, ASSIGNMENT_INDEX),
        ).fetchall()
    )


def _counts(connection) -> tuple[int, int, int]:
    return tuple(
        connection.execute(
            f"SELECT count(*) FROM plm.{table}"  # fixed local table names only
        ).fetchone()[0]
        for table in (
            "rvw_reviews",
            "rvw_review_rounds",
            "rvw_review_assignments",
        )
    )


def _plan(connection, statement: str, params: tuple[object, ...]) -> str:
    connection.execute("SET enable_seqscan=off")
    raw = connection.execute(
        "EXPLAIN (FORMAT JSON, COSTS FALSE) " + statement,
        params,
    ).fetchone()[0]
    return json.dumps(raw, sort_keys=True)


def _verify_indexes(connection) -> None:
    definitions = _index_definitions(connection)
    assert set(definitions) == {REVIEW_INDEX, ASSIGNMENT_INDEX}, definitions
    review = definitions[REVIEW_INDEX]
    assert "(scope, scope_project_key, created_at DESC, review_id DESC)" in review
    assignment = definitions[ASSIGNMENT_INDEX]
    assert "(scope, scope_project_key, reviewer_id, review_round_id)" in assignment
    assert "WHERE (assignment_state = 'PENDING'::text)" in assignment


def _verify_database(repo: Path) -> None:
    fixture = _fixture(repo)
    database = "reviewlist_" + uuid.uuid4().hex[:12]
    with _connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(_url(database))

            # Empty database: up, down and re-up must preserve a clean migration chain.
            command.upgrade(config, "head")
            with _connect(database) as connection:
                assert _version(connection) == HEAD
                _verify_indexes(connection)
            command.downgrade(config, PREVIOUS)
            with _connect(database) as connection:
                assert _version(connection) == PREVIOUS
                assert _index_definitions(connection) == {}
            command.upgrade(config, "head")
            with _connect(database) as connection:
                assert _version(connection) == HEAD
                _verify_indexes(connection)

            # Build valid Review history on 0165, then verify data-preserving lifecycle.
            command.downgrade(config, PREVIOUS)
            with _connect(database) as connection:
                actor = fixture.insert(
                    connection,
                    "auth_users",
                    {
                        "username_display": "Synthetic Review List Actor",
                        "username_normalized": "synthetic review list actor",
                    },
                    "user_id",
                )
                reviewer = fixture.insert(
                    connection,
                    "auth_users",
                    {
                        "username_display": "Synthetic Review List Reviewer",
                        "username_normalized": "synthetic review list reviewer",
                    },
                    "user_id",
                )
                project = fixture.insert(
                    connection,
                    "prj_projects",
                    {
                        "project_code": "RVWLIST",
                        "project_code_normalized": "rvwlist",
                        "name": "Synthetic Review List Project",
                        "created_by": actor,
                    },
                    "project_id",
                )
                for _ in range(24):
                    review_id = fixture.review(connection, actor, project)
                    with connection.transaction():
                        fixture.start(connection, review_id, actor, (reviewer,))
                before = _counts(connection)
                assert before == (24, 24, 24)

            command.upgrade(config, "head")
            with _connect(database) as connection:
                assert _counts(connection) == before
                _verify_indexes(connection)
                review_plan = _plan(
                    connection,
                    """
                    SELECT review_id
                      FROM plm.rvw_reviews
                     WHERE scope=%s AND scope_project_key=%s
                     ORDER BY created_at DESC,review_id DESC
                     LIMIT 10
                    """,
                    ("PROJECT", project),
                )
                assert REVIEW_INDEX in review_plan, review_plan
                assignment_plan = _plan(
                    connection,
                    """
                    SELECT review_round_id
                      FROM plm.rvw_review_assignments
                     WHERE scope=%s AND scope_project_key=%s
                       AND reviewer_id=%s AND assignment_state='PENDING'
                    """,
                    ("PROJECT", project, reviewer),
                )
                assert ASSIGNMENT_INDEX in assignment_plan, assignment_plan
            command.check(config)

            command.downgrade(config, PREVIOUS)
            with _connect(database) as connection:
                assert _version(connection) == PREVIOUS
                assert _counts(connection) == before
                assert _index_definitions(connection) == {}
            command.upgrade(config, "head")
            with _connect(database) as connection:
                assert _version(connection) == HEAD
                assert _counts(connection) == before
                _verify_indexes(connection)
        finally:
            admin.execute(
                """
                SELECT pg_terminate_backend(pid)
                  FROM pg_stat_activity
                 WHERE datname=%s AND pid<>pg_backend_pid()
                """,
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def verify(*, repo: Path, pg_bin: Path, temp_root: Path) -> None:
    repo = repo.resolve(strict=True)
    pg_bin = pg_bin.resolve(strict=True)
    temp_root = temp_root.resolve(strict=True)
    if not temp_root.is_dir() or not str(temp_root).isascii() or not str(pg_bin).isascii():
        raise ValueError("Existing ASCII PostgreSQL binary and temporary roots required")
    if not (pg_bin / "initdb.exe").is_file() or not (pg_bin / "pg_ctl.exe").is_file():
        raise ValueError("PostgreSQL 18 executables required")
    if _command([str(pg_bin / "pg_ctl.exe"), "--version"]) != "pg_ctl (PostgreSQL) 18.6":
        raise ValueError("Expected PostgreSQL 18.6 runtime")
    if not _port_free():
        raise RuntimeError(f"Loopback port {PORT} is occupied; existing instance untouched")

    run = Path(tempfile.mkdtemp(prefix=PREFIX, dir=temp_root))
    if not _safe_run_dir(run, temp_root) or not str(run).isascii():
        raise RuntimeError("Fresh temporary path failed containment check; preserving it")
    data = run / "data"
    log = run / "postgresql.log"
    try:
        _command(
            [
                str(pg_bin / "initdb.exe"),
                f"--pgdata={data}",
                "--username=poc_admin",
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            timeout=120,
        )
        started = subprocess.run(
            [
                str(pg_bin / "pg_ctl.exe"),
                "-D",
                str(data),
                "-l",
                str(log),
                "-o",
                f"-h 127.0.0.1 -p {PORT}",
                "-w",
                "start",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
        if started.returncode:
            details = log.read_text(encoding="utf-8", errors="replace")[-1600:]
            raise RuntimeError(f"Isolated PostgreSQL start failed: {details}")
        _verify_database(repo)
        print(
            "SOL_06_A16_P03_REVIEW_LIST_INDEXES_PG_PASS: "
            "PostgreSQL 18.6 empty/history up-down-re-up, row preservation, "
            "definitions, plans and Alembic drift",
            flush=True,
        )
    finally:
        status = subprocess.run(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if status.returncode == 0:
            _command(
                [
                    str(pg_bin / "pg_ctl.exe"),
                    "-D",
                    str(data),
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                ],
                timeout=60,
            )
        if subprocess.run(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
            capture_output=True,
            timeout=15,
            check=False,
        ).returncode == 0:
            raise RuntimeError(f"Isolated PostgreSQL remains active; preserved at {run}")
        if not _safe_run_dir(run, temp_root):
            raise RuntimeError(f"Temporary data containment changed; preserved at {run}")
        shutil.rmtree(run)
        print("Isolated PostgreSQL stopped; temporary cluster removed", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    verify(repo=args.repo, pg_bin=args.pg_bin, temp_root=args.temp_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
