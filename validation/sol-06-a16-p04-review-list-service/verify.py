"""Verify authorized Review lists on disposable Windows PostgreSQL 18.6."""

from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.review.application.list_contract import ReviewListQuery
from plm_assistant.modules.review.application.list_service import (
    ReviewListError,
    ReviewListService,
)
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead,
)
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectReadRegistry,
)
from plm_assistant.modules.review.infrastructure.list_repository import (
    SqlAlchemyReviewListRepository,
)


PORT = 55432
PREFIX = "plm-review-list-service-"


def _module(path: Path, name: str):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _command(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(
        args, capture_output=True, text=True, errors="replace",
        timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(args[0]).name} exited {result.returncode}: "
            f"{(result.stdout + result.stderr)[-2000:]}"
        )
    return result.stdout.strip()


def _port_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError:
            return False
        return True


def _safe_run_dir(run: Path, root: Path) -> bool:
    root = root.resolve(strict=True)
    run = run.resolve(strict=True)
    return (
        run.parent == root and run.name.startswith(PREFIX)
        and run != root and run.is_dir()
    )


def _url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=PORT, database=database,
    )


def _connect(database: str):
    return psycopg.connect(
        host="127.0.0.1", port=PORT, user="poc_admin",
        dbname=database, autocommit=True,
    )


class SyntheticCurrentSubjectOwner:
    """Test-only HND-02 read owner; not a production authorization source."""

    SUBJECT_TYPE = "HND-02"

    def __init__(self) -> None:
        self.visible: set[uuid.UUID] = set()
        self.fail = False

    def authorize_read(
        self, transaction, *, user_id, project_id, subject_type,
        subject_id, subject_version_id,
    ):
        if self.fail:
            raise RuntimeError("synthetic owner outage")
        if subject_type != self.SUBJECT_TYPE or subject_id not in self.visible:
            return None
        return AuthorizedReviewSubjectRead(
            user_id, project_id, subject_type, subject_id, subject_version_id,
        )


def _expect(service: ReviewListService, query: ReviewListQuery, code: str) -> None:
    try:
        service.list(query)
    except ReviewListError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"Review list unexpectedly accepted: {code}")


def _read_snapshot(connection) -> tuple[object, ...]:
    return tuple(
        connection.execute(statement).fetchall()
        for statement in (
            "SELECT * FROM plm.rvw_reviews ORDER BY review_id",
            "SELECT * FROM plm.rvw_review_rounds ORDER BY review_round_id",
            "SELECT * FROM plm.rvw_review_assignments ORDER BY assignment_id",
            "SELECT * FROM plm.rvw_review_decisions ORDER BY decision_id",
            "SELECT * FROM plm.aud_events ORDER BY audit_event_id",
        )
    )


def _verify_database(repo: Path) -> None:
    schema = _module(
        repo / "validation" / "rvw-01-a02-review-schema" / "verify.py",
        "_review_list_service_schema_fixture",
    )
    auth = _module(
        repo / "validation" / "wfl-01-a03-p05-authorized-initialize"
        / "verify.py",
        "_review_list_service_auth_fixture",
    )
    database = "reviewlist_" + uuid.uuid4().hex[:12]
    runtime = None
    with _connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(_url(database))
            command.upgrade(config, "head")
            runtime = create_database_runtime(_url(database))
            tokens = tuple(bytes([index]) * 32 for index in range(1, 7))
            with _connect(database) as connection:
                users = tuple(
                    auth.user(connection, f"Synthetic list role {index}", token)
                    for index, token in enumerate(tokens)
                )
                project_ids: list[uuid.UUID] = []
                departments: list[uuid.UUID] = []
                for index in range(2):
                    project = schema.insert(
                        connection,
                        "prj_projects",
                        {
                            "project_code": f"RVWLIST{index}",
                            "project_code_normalized": f"rvwlist{index}",
                            "name": f"Synthetic Review List {index}",
                            "created_by": users[0],
                        },
                        "project_id",
                    )
                    department = schema.insert(
                        connection,
                        "prj_departments",
                        {
                            "project_id": project,
                            "department_code": "D",
                            "department_code_normalized": "d",
                            "name": "Synthetic Department",
                        },
                        "department_id",
                    )
                    project_ids.append(project)
                    departments.append(department)
                for user, role in zip(
                    users[:4],
                    (
                        "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                        "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
                    ),
                    strict=True,
                ):
                    schema.insert(
                        connection,
                        "prj_project_members",
                        {
                            "project_id": project_ids[0],
                            "user_id": user,
                            "department_id": departments[0],
                            "project_role": role,
                        },
                        "project_member_id",
                    )
                schema.insert(
                    connection,
                    "prj_project_members",
                    {
                        "project_id": project_ids[1],
                        "user_id": users[4],
                        "department_id": departments[1],
                        "project_role": "PROJECT_MANAGER",
                    },
                    "project_member_id",
                )

                subjects = [uuid.uuid4() for _ in range(5)]
                owner = SyntheticCurrentSubjectOwner()
                owner.visible.update(subjects[:3])

                def create(subject, reviewers, terminal=False):
                    review_id = schema.review(
                        connection, users[0], project_ids[0], subject,
                    )
                    with connection.transaction():
                        round_id, _, _ = schema.start(
                            connection, review_id, users[0], reviewers,
                        )
                    if terminal:
                        with connection.transaction():
                            schema.decide(connection, round_id, reviewers[0])
                    time.sleep(0.002)
                    return review_id, round_id

                old_review, old_round = create(subjects[0], (users[0],))
                terminal_review, _ = create(
                    subjects[1], (users[0],), terminal=True,
                )
                other_review, _ = create(subjects[2], (users[2],))
                hidden_two, _ = create(subjects[3], (users[0],))
                hidden_one, _ = create(subjects[4], (users[0],))

                guard = auth.Guard()
                service = ReviewListService(
                    unit_of_work=runtime.unit_of_work,
                    sessions=SqlAlchemyProjectReadAccess(),
                    projects=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ),
                    license_guard=guard,
                    repository=SqlAlchemyReviewListRepository(),
                    subjects=ProjectReviewSubjectReadRegistry((owner,)),
                )
                before_reads = _read_snapshot(connection)
                first = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0], page_size=2,
                ))
                assert first.items == () and first.has_more
                assert first.next_position is not None
                second = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0],
                    before=first.next_position, page_size=2,
                ))
                assert [item.review_id for item in second.items] == [
                    other_review, terminal_review,
                ]
                assert second.has_more and second.next_position is not None
                assert second.items[0].active_round is not None
                assert second.items[0].active_round.my_assignment is None
                assert second.items[1].active_round is None
                third = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0],
                    before=second.next_position, page_size=2,
                ))
                assert [item.review_id for item in third.items] == [old_review]
                assert not third.has_more and third.next_position is None

                pending = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0],
                    view="my_pending", page_size=10,
                ))
                assert [item.review_id for item in pending.items] == [old_review]
                assert pending.items[0].active_round.my_assignment.state == "PENDING"
                customer_pending = service.list(ReviewListQuery(
                    tokens[2], uuid.uuid4(), project_ids[0],
                    view="my_pending", page_size=10,
                ))
                assert [item.review_id for item in customer_pending.items] == [
                    other_review,
                ]
                for token in tokens[1:4]:
                    all_page = service.list(ReviewListQuery(
                        token, uuid.uuid4(), project_ids[0], page_size=10,
                    ))
                    assert {item.review_id for item in all_page.items} == {
                        old_review, terminal_review, other_review,
                    }
                assert _read_snapshot(connection) == before_reads

                _expect(
                    service,
                    ReviewListQuery(
                        tokens[4], uuid.uuid4(), project_ids[0], page_size=10,
                    ),
                    "RESOURCE_NOT_FOUND",
                )
                _expect(
                    service,
                    ReviewListQuery(
                        b"x" * 32, uuid.uuid4(), project_ids[0], page_size=10,
                    ),
                    "AUTH_ACCESS_DENIED",
                )
                guard.enabled = False
                _expect(
                    service,
                    ReviewListQuery(
                        tokens[0], uuid.uuid4(), project_ids[0], page_size=10,
                    ),
                    "LICENSE_OPERATION_DENIED",
                )
                guard.enabled = True
                owner.fail = True
                _expect(
                    service,
                    ReviewListQuery(
                        tokens[0], uuid.uuid4(), project_ids[0], page_size=10,
                    ),
                    "REVIEW_UNAVAILABLE",
                )
                owner.fail = False

                membership = connection.execute(
                    """
                    SELECT project_member_id
                      FROM plm.prj_project_members
                     WHERE project_id=%s AND user_id=%s
                    """,
                    (project_ids[0], users[0]),
                ).fetchone()[0]
                connection.execute(
                    """
                    UPDATE plm.prj_project_members
                       SET state='SUSPENDED',lock_version=lock_version+1
                     WHERE project_member_id=%s
                    """,
                    (membership,),
                )
                _expect(
                    service,
                    ReviewListQuery(
                        tokens[0], uuid.uuid4(), project_ids[0], page_size=10,
                    ),
                    "RESOURCE_NOT_FOUND",
                )
                connection.execute(
                    """
                    UPDATE plm.prj_project_members
                       SET state='ACTIVE',lock_version=lock_version+1
                     WHERE project_member_id=%s
                    """,
                    (membership,),
                )

                with connection.transaction():
                    schema.decide(connection, old_round, users[0])
                after_decision = _read_snapshot(connection)
                pending = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0],
                    view="my_pending", page_size=10,
                ))
                assert pending.items == ()
                all_page = service.list(ReviewListQuery(
                    tokens[0], uuid.uuid4(), project_ids[0], page_size=10,
                ))
                assert old_review in {item.review_id for item in all_page.items}
                assert _read_snapshot(connection) == after_decision
                assert set(connection.execute(
                    """
                    SELECT review_id
                      FROM plm.rvw_reviews
                     WHERE project_id=%s
                    """,
                    (project_ids[0],),
                ).fetchall()) == {
                    (old_review,), (terminal_review,), (other_review,),
                    (hidden_two,), (hidden_one,),
                }
            command.check(config)
        finally:
            if runtime is not None:
                runtime.dispose()
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
    data, log = run / "data", run / "postgresql.log"
    try:
        _command([
            str(pg_bin / "initdb.exe"), f"--pgdata={data}",
            "--username=poc_admin", "--auth=trust", "--encoding=UTF8",
            "--locale=C",
        ])
        started = subprocess.run(
            [
                str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start",
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
            "SOL_06_A16_P04_REVIEW_LIST_SERVICE_PG_PASS: real Session/Project, "
            "all/my_pending, hidden empty page continuation, terminal history, "
            "current revocation and read-only snapshots; synthetic Subject/License",
            flush=True,
        )
    finally:
        status = subprocess.run(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
            capture_output=True, timeout=15, check=False,
        )
        if status.returncode == 0:
            _command([
                str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast",
                "-w", "stop",
            ], timeout=60)
        if subprocess.run(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
            capture_output=True, timeout=15, check=False,
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
