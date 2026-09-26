"""Necessary account/project reviewer qualification, not Subject or customer approval."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Event
import uuid
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService, ReviewReviewerEligibilityError
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

spec = spec_from_file_location("_reviewer_fixture", Path(__file__).resolve().parents[1] / "rvw-01-a05-authorized-read" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
schema, auth = fixture.schema, fixture.auth


def main():
    name, runtime = "rvwusers_"+uuid.uuid4().hex[:12], None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            with schema.connect(name) as db:
                users = [auth.user(db, f"Synthetic reviewer {i}", bytes([i+1])*32, "DEPLOYMENT_ADMIN" if i==2 else "NONE") for i in range(3)]
                project = schema.insert(db, "prj_projects", dict(project_code="RQ", project_code_normalized="rq", name="Synthetic reviewers", created_by=users[0]), "project_id")
                department = schema.insert(db, "prj_departments", dict(project_id=project, department_code="D", department_code_normalized="d", name="Synthetic department"), "department_id")
                for actor, role in zip(users, ("CUSTOMER_MANAGER", "CUSTOMER_MEMBER")):
                    schema.insert(db, "prj_project_members", dict(project_id=project, user_id=actor, department_id=department, project_role=role), "project_member_id")
                roles = frozenset({"CUSTOMER_MANAGER", "CUSTOMER_MEMBER"})
                service = ProjectReviewerQualificationService(users=SqlAlchemyReviewUserAccess(), projects=SqlAlchemyProjectAuthorizationRepository())
                def qualify(candidates=tuple(users[:2]), p=project):
                    with runtime.unit_of_work() as tx:
                        return service.qualify_in_transaction(tx, project_id=p, reviewer_ids=candidates, allowed_roles=roles)
                def deny(candidates=tuple(users[:2]), p=project):
                    try: qualify(candidates, p)
                    except ReviewReviewerEligibilityError: pass
                    else: raise AssertionError("ineligible reviewers accepted")
                def snapshot():
                    return tuple(tuple(db.execute(q)) for q in (
                        "SELECT user_id,state,lock_version FROM plm.auth_users ORDER BY user_id",
                        "SELECT project_member_id,state,effective_at,ended_at,lock_version FROM plm.prj_project_members ORDER BY project_member_id",
                        "SELECT department_id,state,lock_version FROM plm.prj_departments ORDER BY department_id",
                        "SELECT project_id,state,lock_version FROM plm.prj_projects ORDER BY project_id"))
                before = snapshot()
                assert tuple(v.user_id for v in qualify()) == tuple(users[:2])
                deny((users[2],)); deny((uuid.uuid4(),)); deny(p=uuid.uuid4()); deny((users[0], users[0]))
                assert snapshot() == before
                for table, where, rejected, restored in (
                    ("auth_users", ("user_id",users[0]), "state='DISABLED'", "state='ENABLED'"),
                    ("prj_project_members", ("user_id",users[0]), "state='SUSPENDED'", "state='ACTIVE'"),
                    ("prj_project_members", ("user_id",users[0]), "state='REMOVED',ended_at=statement_timestamp()", "state='ACTIVE',ended_at=NULL"),
                    ("prj_project_members", ("user_id",users[0]), "effective_at=statement_timestamp()+interval '1 hour'", "effective_at=statement_timestamp()-interval '1 minute'"),
                    ("prj_departments", ("department_id",department), "state='INACTIVE'", "state='ACTIVE'"),
                    ("prj_projects", ("project_id",project), "state='ARCHIVED'", "state='ACTIVE'"),
                    ("prj_project_members", ("user_id",users[0]), "project_role='IMPLEMENTATION_MEMBER'", "project_role='CUSTOMER_MANAGER'"),
                ):
                    # Identifiers and updates are fixed internal fixture literals, not user input.
                    query = sql.SQL("UPDATE plm.{} SET {},lock_version=lock_version+1 WHERE {}=%s")
                    db.execute(query.format(sql.Identifier(table), sql.SQL(rejected), sql.Identifier(where[0])), (where[1],))
                    deny()
                    db.execute(query.format(sql.Identifier(table), sql.SQL(restored), sql.Identifier(where[0])), (where[1],))
                    assert len(qualify()) == 2
                entered, release = Event(), Event()
                def waiting():
                    with runtime.unit_of_work() as tx:
                        result = service.qualify_in_transaction(tx, project_id=project, reviewer_ids=tuple(users[:2]), allowed_roles=roles)
                        entered.set()
                        assert release.wait(timeout=10)
                        return result
                before = snapshot()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(waiting)
                    try:
                        assert entered.wait(timeout=10)
                        with schema.connect(name) as rival:
                            rival.execute("SET lock_timeout='150ms'")
                            for statement, parameter in (
                                ("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", users[0]),
                                ("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s", users[0]),
                                ("UPDATE plm.prj_departments SET state='INACTIVE',lock_version=lock_version+1 WHERE department_id=%s", department),
                                ("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", project),
                            ):
                                try: rival.execute(statement, (parameter,))
                                except psycopg.errors.LockNotAvailable: pass
                                else: raise AssertionError("reviewer qualification lock escaped caller transaction")
                    finally: release.set()
                    assert len(future.result(timeout=10)) == 2
                assert snapshot() == before
                db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (users[0],))
                deny()
                assert db.execute("SELECT count(*) FROM plm.rvw_review_assignments").fetchone()[0] == 0
            print("RVW-02-A03 PASS: real enabled users/current scoped members/departments/roles, suspended/removed/future/disabled/admin/cross-project rejection, caller locks and no assignments; necessary facts only, not Subject eligibility/start/Gate")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
