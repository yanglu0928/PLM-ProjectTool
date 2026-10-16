"""Owned disposable DB: real Auth/CSRF/Project/Audit/receipts, synthetic Owner/License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.create_review import CreateReview, AuthorizedReviewCreation, ReviewCreateService, ReviewCreateError
from plm_assistant.modules.review.infrastructure.create_repository import SqlAlchemyReviewCreationRepository

spec = spec_from_file_location("_review_create_fixture", Path(__file__).resolve().parents[1] / "rvw-01-a05-authorized-read" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
schema, auth = fixture.schema, fixture.auth


def main():
    name, runtime = "rvwcreate_"+uuid.uuid4().hex[:12], None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            with schema.connect(name) as db:
                tokens = [bytes([i])*32 for i in range(1, 6)]
                users = [auth.user(db, f"Synthetic create role {i}", token, "DEPLOYMENT_ADMIN" if i==4 else "NONE") for i, token in enumerate(tokens)]
                project = schema.insert(db, "prj_projects", dict(project_code="RC", project_code_normalized="rc", name="Synthetic Review create", created_by=users[0]), "project_id")
                department = schema.insert(db, "prj_departments", dict(project_id=project, department_code="D", department_code_normalized="d", name="Synthetic department"), "department_id")
                for actor, role in zip(users, ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER")):
                    schema.insert(db, "prj_project_members", dict(project_id=project, user_id=actor, department_id=department, project_role=role), "project_member_id")
                command_value = CreateReview(tokens[0], auth.CSRF, uuid.uuid4(), project, "HND-02", uuid.uuid4(), uuid.uuid4())

                class SyntheticOwner:
                    allowed = True
                    replay_allowed = True
                    def authorize_create(self, tx, **k):
                        return AuthorizedReviewCreation(**k, policy_code="CUSTOMER_ALL_V1") if self.allowed else None
                    def authorize_replay(self, tx, **k): return self.replay_allowed

                owner, guard = SyntheticOwner(), auth.Guard()
                dependencies = dict(unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=guard, repository=SqlAlchemyReviewCreationRepository(), receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()), subjects=owner)
                service = ReviewCreateService(**dependencies)
                def create(value=command_value, key="synthetic-review-key", use=service):
                    return use.create_idempotent(value, idempotency_key=key)
                def deny(value, code, key="synthetic-review-key", use=service):
                    try: create(value, key, use)
                    except ReviewCreateError as error: assert error.code == code, (error.code, code)
                    else: raise AssertionError("Review creation rejection bypassed")
                def snapshot():
                    return schema.snapshot(db), tuple(db.execute("SELECT * FROM plm.plt_idempotency_receipts ORDER BY receipt_id")), tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                before = snapshot()
                for token in tokens[1:]: deny(replace(command_value, session_token=token), "RESOURCE_NOT_FOUND")
                deny(replace(command_value, csrf_token=b"x"*32), "AUTH_ACCESS_DENIED")
                deny(replace(command_value, project_id=uuid.uuid4()), "RESOURCE_NOT_FOUND")
                deny(command_value, "RESOURCE_NOT_FOUND", use=ReviewCreateService(**(dependencies | dict(subjects=None))))
                owner.allowed = False
                deny(command_value, "RESOURCE_NOT_FOUND")
                owner.allowed = True
                guard.enabled = False
                deny(command_value, "LICENSE_OPERATION_DENIED")
                guard.enabled = True
                assert snapshot() == before
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(), range(2)))
                result = results[0]
                assert results[1] == result == create()
                assert db.execute("SELECT count(*) FROM plm.rvw_reviews").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_CREATED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE state='COMPLETED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.rvw_review_rounds").fetchone()[0] == 0
                before = snapshot()
                deny(replace(command_value, subject_version_id=uuid.uuid4()), "CONFLICT_IDEMPOTENCY")
                owner.replay_allowed = False
                deny(command_value, "RESOURCE_NOT_FOUND")
                owner.replay_allowed = True
                assert snapshot() == before
                for overrides in (dict(audit=auth.FailedAudit()),):
                    deny(command_value, "REVIEW_UNAVAILABLE", key="synthetic-audit-failure", use=ReviewCreateService(**(dependencies | overrides)))
                    assert snapshot() == before
                class FailingReceipts(SqlAlchemyIdempotencyReceipts):
                    def complete(self, *a, **k):
                        super().complete(*a, **k)
                        raise RuntimeError("synthetic receipt failure")
                deny(command_value, "REVIEW_UNAVAILABLE", key="synthetic-receipt-failure", use=ReviewCreateService(**(dependencies | dict(receipts=FailingReceipts()))))
                assert snapshot() == before
                with db.transaction():
                    round_id, _, _ = schema.start(db, result.review_id, users[0], users[2:4])
                    schema.decide(db, round_id, users[2])
                    schema.decide(db, round_id, users[3])
                assert db.execute("SELECT review_state FROM plm.rvw_reviews WHERE review_id=%s", (result.review_id,)).fetchone()[0] == "APPROVED"
                assert create() == result  # immutable original ref, not current APPROVED projection
                assert create(key="synthetic-new-create-key").review_id != result.review_id
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", (project,))
                before = snapshot()
                deny(command_value, "PROJECT_ARCHIVED")
                assert snapshot() == before
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (users[0],))
                deny(command_value, "AUTH_ACCESS_DENIED")
            print("RVW-01-A07 PASS: real Session/CSRF/PM/Project/Audit/receipt, concurrent replay once, changed payload and missing Owner denial, immutable original ref after round, audit/receipt full rollback, archived/revoked rejection; synthetic Owner/License, no HTTP/start/Gate")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
