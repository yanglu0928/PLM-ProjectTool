"""Windows 11/PostgreSQL 18 proof for Handover Analysis state Owner."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.handover.application.change_analysis import (
    ArchiveHandoverAnalysis, HandoverAnalysisStateError,
    HandoverAnalysisStateService, PatchHandoverAnalysis,
)
from plm_assistant.modules.handover.infrastructure.analysis_state_repository import (
    SqlAlchemyHandoverAnalysisStateRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "hnd_analysis_state_fixture",
)
connect, seed_user = fixture.connect, fixture.seed_user
Guard, CSRF = fixture.Guard, fixture.CSRF


def expect(code: str, action) -> None:
    try:
        action()
    except HandoverAnalysisStateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = "hnd01a05a03_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token, foreign_token = (
        bytes([value]) * 32 for value in (112, 105, 99, 102)
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20261005_0101")
            command.upgrade(config, "head")
            command.check(config)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "State PM", "NONE", pm_token)
                    implementer = seed_user(db, "State IM", "NONE", impl_token)
                    customer = seed_user(db, "State Customer", "NONE", customer_token)
                    foreign = seed_user(db, "State Foreign", "NONE", foreign_token)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDSTATE','hndstate','Handover State',%s) "
                        "RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    foreign_project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDSTATE2','hndstate2','Foreign',%s) "
                        "RETURNING project_id", (foreign,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'HND','hnd','Handover') RETURNING department_id",
                        (project,),
                    ).fetchone()[0]
                    foreign_department = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'HND','hnd','Foreign') RETURNING department_id",
                        (foreign_project,),
                    ).fetchone()[0]
                    for user, role in (
                        (pm, "PROJECT_MANAGER"),
                        (implementer, "IMPLEMENTATION_MEMBER"),
                        (customer, "CUSTOMER_MEMBER"),
                    ):
                        db.execute(
                            "INSERT INTO plm.prj_project_members"
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,%s)",
                            (project, user, department, role),
                        )
                    db.execute(
                        "INSERT INTO plm.prj_project_members"
                        "(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                        (foreign_project, foreign, foreign_department),
                    )
                    analyses = [uuid.uuid4() for _ in range(5)]
                    foreign_analysis = uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for index, analysis_id in enumerate(analyses):
                            db.execute(
                                "INSERT INTO plm.hnd_analyses"
                                "(handover_analysis_id,project_id,analysis_purpose,"
                                "source_set_ref,analysis_state,created_by,lock_version) "
                                "VALUES (%s,%s,%s,%s,'ACTIVE',%s,0)",
                                (analysis_id, project, f"Purpose {index}",
                                 "sha256:" + str(index) * 64, pm),
                            )
                        db.execute(
                            "INSERT INTO plm.hnd_analyses"
                            "(handover_analysis_id,project_id,analysis_purpose,"
                            "source_set_ref,analysis_state,created_by,lock_version) "
                            "VALUES (%s,%s,'Foreign',%s,'ACTIVE',%s,0)",
                            (foreign_analysis, foreign_project,
                             "sha256:" + "f" * 64, foreign),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_analysis_versions"
                            "(handover_analysis_version_id,handover_analysis_id,"
                            "project_id,version_no,version_state,source_set_ref,"
                            "capability_baseline_id,capability_baseline_version_ref,"
                            "content_fingerprint,declared_source_count,"
                            "declared_item_count,declared_evidence_count,"
                            "declared_capability_ref_count,declared_ai_task_count,"
                            "review_ref,review_round_ref,created_by) VALUES "
                            "(%s,%s,%s,1,'IN_REVIEW',%s,%s,%s,%s,1,1,0,0,0,%s,%s,%s)",
                            (uuid.uuid4(), analyses[3], project,
                             "sha256:" + "3" * 64, uuid.uuid4(), uuid.uuid4(),
                             b"v" * 32, uuid.uuid4(), uuid.uuid4(), pm),
                        )

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )

                def service(custom_guard=None, audit=None):
                    return HandoverAnalysisStateService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectWriteAccess(),
                        license_guard=custom_guard or guard,
                        authorization=authorization,
                        repository=SqlAlchemyHandoverAnalysisStateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    )

                def patch(token, analysis_id, expected, purpose,
                          selected_project=project):
                    return PatchHandoverAnalysis(
                        token, CSRF, uuid.uuid4(), selected_project,
                        analysis_id, expected, purpose,
                    )

                def archive(token, analysis_id, expected, key,
                            selected_project=project):
                    return ArchiveHandoverAnalysis(
                        token, CSRF, uuid.uuid4(), selected_project,
                        analysis_id, expected, key,
                    )

                pm_result = service().patch(patch(
                    pm_token, analyses[0], 0, "  Ｔｅｃｈｎｉｃａｌ handover  ",
                ))
                assert (pm_result.analysis_purpose, pm_result.etag) == (
                    "Technical handover", '"v1"',
                )
                impl_result = service().patch(patch(
                    impl_token, analyses[1], 0, "Implementation handover",
                ))
                assert impl_result.etag == '"v1"'
                expect("RESOURCE_NOT_FOUND", lambda: service().patch(patch(
                    customer_token, analyses[2], 0, "Customer attempt",
                )))
                expect("CONFLICT_VERSION", lambda: service().patch(patch(
                    pm_token, analyses[0], 0, "Stale",
                )))
                expect("RESOURCE_NOT_FOUND", lambda: service().patch(patch(
                    pm_token, foreign_analysis, 0, "Cross project",
                )))
                expect("HANDOVER_STATE_CONFLICT", lambda: service().patch(patch(
                    pm_token, analyses[3], 0, "Review drift",
                )))
                expect("HANDOVER_STATE_CONFLICT", lambda: service().archive(archive(
                    pm_token, analyses[3], 0, str(uuid.uuid4()),
                )))
                archive_key = str(uuid.uuid4())
                archived = service().archive(archive(
                    pm_token, analyses[0], 1, archive_key,
                ))
                replayed = service().archive(archive(
                    pm_token, analyses[0], 1, archive_key,
                ))
                assert archived == replayed
                assert (archived.analysis_state, archived.etag) == ("ARCHIVED", '"v2"')
                expect("RESOURCE_NOT_FOUND", lambda: service().archive(archive(
                    impl_token, analyses[1], 1, str(uuid.uuid4()),
                )))
                expect("HANDOVER_STATE_CONFLICT", lambda: service().patch(patch(
                    pm_token, analyses[0], 2, "Cannot restore",
                )))
                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(expired).patch(patch(
                    pm_token, analyses[2], 0, "License denied",
                )))
                expect("HANDOVER_UNAVAILABLE", lambda: service(
                    audit=AuditService(FailedAudit()),
                ).patch(patch(pm_token, analyses[4], 0, "Must roll back")))

                with connect(name) as db:
                    rolled_back = db.execute(
                        "SELECT analysis_purpose,lock_version FROM plm.hnd_analyses "
                        "WHERE handover_analysis_id=%s", (analyses[4],),
                    ).fetchone()
                    assert rolled_back == ("Purpose 4", 0), rolled_back
                    audit_counts = dict(db.execute(
                        "SELECT action,count(*) FROM plm.aud_events "
                        "WHERE target_owner_module='handover' AND action IN "
                        "('HND_ANALYSIS_PATCHED','HND_ANALYSIS_ARCHIVED') "
                        "GROUP BY action"
                    ).fetchall())
                    assert audit_counts == {
                        "HND_ANALYSIS_PATCHED": 2,
                        "HND_ANALYSIS_ARCHIVED": 1,
                    }, audit_counts
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_HND_ANALYSIS_ARCHIVE'"
                    ).fetchone()[0] == 1
                    try:
                        db.execute(
                            "UPDATE plm.hnd_analyses SET analysis_purpose='Bypass',"
                            "updated_by=%s,updated_at=statement_timestamp(),"
                            "lock_version=lock_version+1 WHERE handover_analysis_id=%s",
                            (pm, analyses[0]),
                        )
                    except Exception:
                        db.rollback()
                    else:
                        raise AssertionError("archived Analysis accepted a metadata write")

                try:
                    command.downgrade(config, "20261005_0101")
                except Exception as error:
                    assert "state-owner history prevents downgrade" in str(error)
                else:
                    raise AssertionError("state-owner history downgrade was accepted")
                print(
                    "HND_01_A05_A03_ANALYSIS_STATE_OWNER_PASS: migration roundtrip, "
                    "narrow metadata/archive guard, PM/implementer roles, project "
                    "isolation, strong version, Review fence, exact archive replay, "
                    "License/audit rollback, archived write rejection and historical "
                    "downgrade refusal verified on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
