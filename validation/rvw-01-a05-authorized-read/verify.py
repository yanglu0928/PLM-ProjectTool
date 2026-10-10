"""Real Session/Project/Review persistence; synthetic Owner and License only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Event
import uuid
import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead, ReviewReadQuery, ReviewReadService, ReviewReadError,
)
from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository


def fixture(directory, name):
    spec = spec_from_file_location(name, Path(__file__).resolve().parents[1] / directory / "verify.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = fixture("rvw-01-a02-review-schema", "_review_schema_fixture")
auth = fixture("wfl-01-a03-p05-authorized-initialize", "_review_auth_fixture")


def main():
    name, runtime = "rvwread_"+uuid.uuid4().hex[:12], None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            tokens = [bytes([i])*32 for i in range(1, 6)]
            with schema.connect(name) as db:
                users = [auth.user(db, f"Synthetic review role {i}", token, "DEPLOYMENT_ADMIN" if i == 4 else "NONE") for i, token in enumerate(tokens)]
                project = schema.insert(db, "prj_projects", dict(project_code="RREAD", project_code_normalized="rread", name="Synthetic Review read", created_by=users[0]), "project_id")
                department = schema.insert(db, "prj_departments", dict(project_id=project, department_code="D", department_code_normalized="d", name="Synthetic department"), "department_id")
                for actor, role in zip(users, ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER")):
                    schema.insert(db, "prj_project_members", dict(project_id=project, user_id=actor, department_id=department, project_role=role), "project_member_id")
                review = schema.review(db, users[0], project)
                with db.transaction():
                    old_round, _, old_version = schema.start(db, review, users[0], users[2:4])
                    schema.decide(db, old_round, users[2])
                    schema.decide(db, old_round, users[3])
                with db.transaction():
                    current_round, _, _ = schema.start(db, review, users[0], users[2:4])
                subject = db.execute("SELECT subject_type,subject_id FROM plm.rvw_reviews WHERE review_id=%s", (review,)).fetchone()

                class SyntheticOwner:
                    deny_version = False
                    wait = False
                    entered, release = Event(), Event()
                    def authorize_read(self, tx, **k):
                        if (k["user_id"] not in users[:4] or k["project_id"] != project
                                or (k["subject_type"], k["subject_id"]) != subject
                                or self.deny_version and k["subject_version_id"] is not None):
                            return None
                        if self.wait:
                            self.entered.set()
                            assert self.release.wait(timeout=10)
                        return AuthorizedReviewSubjectRead(**k)

                owner, guard = SyntheticOwner(), auth.Guard()
                dependencies = dict(unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectReadAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=guard, repository=SqlAlchemyReviewSnapshotReadRepository())
                reads = ReviewReadService(**dependencies, subjects=owner)
                query = ReviewReadQuery(tokens[0], project, review, uuid.uuid4(), old_round)
                def deny(value, code, service=reads):
                    try: service.get(value)
                    except ReviewReadError as error: assert error.code == code, (error.code, code)
                    else: raise AssertionError("unauthorized Review read accepted")
                before = schema.snapshot(db)
                for token in tokens[:4]:
                    result = reads.get(replace(query, session_token=token))
                    assert result.review.state == "IN_REVIEW"
                    assert result.fixed_round.progress.state.value == "APPROVED"
                    assert result.fixed_round.subject_version_id == old_version
                deny(replace(query, session_token=tokens[4]), "RESOURCE_NOT_FOUND")
                deny(replace(query, project_id=uuid.uuid4()), "RESOURCE_NOT_FOUND")
                deny(replace(query, review_id=uuid.uuid4()), "RESOURCE_NOT_FOUND")
                deny(replace(query, round_id=uuid.uuid4()), "RESOURCE_NOT_FOUND")
                deny(replace(query, session_token=b"x"*32), "AUTH_ACCESS_DENIED")
                deny(query, "RESOURCE_NOT_FOUND", ReviewReadService(**dependencies))
                owner.deny_version = True
                deny(query, "RESOURCE_NOT_FOUND")
                assert reads.get(replace(query, round_id=None)).fixed_round is None
                owner.deny_version = False
                guard.enabled = False
                deny(query, "LICENSE_OPERATION_DENIED")
                guard.enabled = True
                assert schema.snapshot(db) == before
                # Real Auth/Project/Review locks held while synthetic Owner checks.
                owner.wait = True
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(reads.get, query)
                    try:
                        assert owner.entered.wait(timeout=10)
                        with schema.connect(name) as rival:
                            rival.execute("SET lock_timeout='150ms'")
                            for statement, params in (
                                ("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s", (users[0],)),
                                ("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (users[0],)),
                                ("UPDATE plm.rvw_reviews SET lock_version=lock_version+1 WHERE review_id=%s", (review,)),
                            ):
                                try: rival.execute(statement, params)
                                except psycopg.errors.LockNotAvailable: pass
                                else: raise AssertionError("authorization lock escaped caller transaction")
                    finally:
                        owner.release.set()
                    assert future.result(timeout=10).fixed_round.progress.state.value == "APPROVED"
                owner.wait = False
                assert schema.snapshot(db) == before
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", (project,))
                assert reads.get(query).review.state == "IN_REVIEW"
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s", (users[0],))
                deny(query, "RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (users[1],))
                deny(replace(query, session_token=tokens[1]), "AUTH_ACCESS_DENIED")
                assert db.execute("SELECT count(*) FROM plm.rvw_review_rounds WHERE review_id=%s", (review,)).fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
            print("RVW-01-A05 PASS: real Session/Project four-role authorization, fixed history, missing Owner/version denial, admin/cross-project/revoked/suspended/License rejection, caller locks/no Review writes; synthetic Owner/License, no HTTP/Gate")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
