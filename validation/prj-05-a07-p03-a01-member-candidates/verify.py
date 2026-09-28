"""Disposable PostgreSQL 18 verification for CR-PRJ-006 candidate lookup."""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.auth.infrastructure.project_member_candidate_access import SqlAlchemyProjectMemberCandidateAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.member_candidates import create_project_member_candidate_router
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.member_candidates import ProjectMemberCandidateService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_candidate_repository import SqlAlchemyMemberCandidateMembership


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
USER = "poc_admin"


class Guard:
    enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class Sessions:
    def __init__(self, tokens):
        self.tokens = frozenset(tokens)

    def validate(self, token, *, csrf_token, require_csrf):
        if token not in self.tokens or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def run(*args, detached=False):
    result = subprocess.run(args, stdout=subprocess.DEVNULL if detached else subprocess.PIPE,
                            stderr=subprocess.DEVNULL if detached else subprocess.PIPE,
                            text=True, timeout=60, check=False)
    if result.returncode:
        raise AssertionError(f"PostgreSQL tool failed ({result.returncode}): {(result.stderr or '')[-1200:]}")


def reserve_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def user(db, name, token=None, *, disabled=False, admin=False):
    uid = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id",
        (name, name.casefold(), "DEPLOYMENT_ADMIN" if admin else "NONE"),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id",
        (uid,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET state=%s,credential_version=1,active_password_credential_id=%s WHERE user_id=%s",
        ("DISABLED" if disabled else "ENABLED", credential, uid),
    )
    if token is not None:
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,"
            "idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,"
            "statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')",
            (hashlib.sha256(token).digest(), hashlib.sha256(b"c" * 32).digest(), uid),
        )
    return uid


def main():
    with tempfile.TemporaryDirectory(prefix="prj_candidate_pg_") as scratch:
        install = Path(scratch) / "pgsql"
        for name in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / name, install / name)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for script in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(script, install / "share/extension" / script.name)
        bin_dir = install / "bin"
        data = Path(scratch) / "data"
        port = reserve_port()
        run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", USER, "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(Path(scratch) / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        try:
            dbname = "candidate_" + uuid.uuid4().hex[:12]
            with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                 dbname="postgres", autocommit=True) as admin:
                admin.execute("CREATE DATABASE " + dbname)
            url = URL.create("postgresql+psycopg", username=USER,
                             host="127.0.0.1", port=port, database=dbname)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                tokens = {name: bytes([index]) * 32 for index, name in enumerate(
                    ("pm", "other_pm", "customer", "admin"), start=31)}
                with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                     dbname=dbname, autocommit=True) as db:
                    ids = {name: user(db, "Synthetic " + name, token,
                                      admin=name == "admin") for name, token in tokens.items()}
                    target = user(db, "Target")
                    disabled = user(db, "Disabled", disabled=True)
                    assigned = user(db, "Assigned")
                    p1 = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm"],),
                    ).fetchone()[0]
                    p2 = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["other_pm"],),
                    ).fetchone()[0]
                    d1 = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,),
                    ).fetchone()[0]
                    d2 = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'D2','d2','Second') RETURNING department_id", (p2,),
                    ).fetchone()[0]
                    for project, department, name, role in (
                        (p1, d1, "pm", "PROJECT_MANAGER"),
                        (p2, d2, "other_pm", "PROJECT_MANAGER"),
                        (p1, d1, "customer", "CUSTOMER_MANAGER"),
                    ):
                        db.execute(
                            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,%s)", (project, ids[name], department, role),
                        )
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')", (p2, assigned, d2),
                    )
                guard = Guard()
                service = ProjectMemberCandidateService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberCandidateAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ),
                    membership=SqlAlchemyMemberCandidateMembership(),
                    rate=SqlAlchemyLoginRateRepository(),
                )
                router = create_project_member_candidate_router(
                    sessions=Sessions(tokens.values()), candidates=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                with TestClient(create_app(project_member_candidate_router=router),
                                base_url="https://plm.example.test") as client:
                    def get(name, username="Target", project=p1):
                        return client.post(f"/api/v1/projects/{project}/member-candidates:resolve",
                                          json={"username": username}, headers={
                                              "cookie": "plm_session=" + tokens[name].hex(),
                                              "origin": "https://plm.example.test",
                                              "x-csrf-token": (b"c" * 32).hex(),
                                          })

                    hit = get("pm", " TARGET ")
                    assert hit.status_code == 200, hit.text
                    assert hit.json()["data"] == {"candidate": {
                        "user_id": str(target), "display_name": "Target",
                    }}
                    for name in ("Missing", "Disabled", "Assigned"):
                        answer = get("pm", name)
                        assert answer.status_code == 200 and answer.json()["data"] == {"candidate": None}
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("UPDATE plm.prj_project_members SET state='REMOVED', "
                                   "ended_at=statement_timestamp() WHERE user_id=%s", (assigned,))
                    assert get("pm", "Assigned").json()["data"]["candidate"]["user_id"] == str(assigned)
                    for name, project in (("customer", p1), ("other_pm", p1), ("admin", p1), ("pm", p2)):
                        assert get(name, project=project).status_code == 404
                    guard.enabled = False
                    assert get("pm").status_code == 403
                    guard.enabled = True
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (target,))
                    assert get("pm").json()["data"] == {"candidate": None}
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s", (target,))
                        db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER' "
                                   "WHERE project_id=%s AND user_id=%s", (p1, ids["pm"]))
                    assert get("pm").status_code == 404
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' "
                                   "WHERE project_id=%s AND user_id=%s", (p1, ids["pm"]))
                        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                    assert get("pm").status_code == 409
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (p1,))
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(), "
                                   "revoke_reason='LOGOUT', lock_version=lock_version+1 WHERE user_id=%s",
                                   (ids["other_pm"],))
                    assert get("other_pm", project=p2).status_code == 401
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("DELETE FROM plm.auth_login_rate_buckets")
                    for _ in range(10):
                        assert get("pm").status_code == 200
                    assert get("pm").status_code == 429
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        db.execute("DELETE FROM plm.auth_login_rate_buckets")
                    for index in range(30):
                        assert get("pm", f"Missing {index}").status_code == 200
                    assert get("pm", "Missing overflow").status_code == 429
                    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                         dbname=dbname, autocommit=True) as db:
                        assert db.execute("SELECT count(*) FROM plm.prj_project_members").fetchone()[0] == 4
                        assert db.execute("SELECT count(*) FROM plm.auth_login_rate_buckets").fetchone()[0] == 31
                        assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
                print("Candidate lookup PASS: actual PG18 current Session/User/Project/Member, "
                      "uniform miss, role/project/license denial, 10-target/30-actor durable limits, no member/Audit writes")
            finally:
                runtime.dispose()
        finally:
            run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    main()
