"""Windows 11/PostgreSQL 18 proof for Handover Analysis read ownership."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisReadError, HandoverAnalysisReadQuery,
    HandoverAnalysisReadService,
)
from plm_assistant.modules.handover.infrastructure.analysis_read_repository import (
    SqlAlchemyHandoverAnalysisReadRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
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
    "hnd_analysis_read_fixture",
)
connect, seed_user, Guard = fixture.connect, fixture.seed_user, fixture.Guard


def expect(code: str, action) -> None:
    try:
        action()
    except HandoverAnalysisReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    name = "hnd01a05a02_" + uuid.uuid4().hex[:8]
    tokens = [bytes([value]) * 32 for value in (112, 105, 109, 99, 102)]
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
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    roles = ("PM", "IM", "CM", "CUSTOMER", "FOREIGN")
                    users = [seed_user(db, "Analysis " + role, "NONE", token)
                             for role, token in zip(roles, tokens)]
                    pm, implementer, customer_manager, customer, foreign = users
                    project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDANREAD','hndanread','Analysis Read',%s) "
                        "RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    foreign_project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDANOTHER','hndanother','Foreign',%s) "
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
                        (customer_manager, "CUSTOMER_MANAGER"),
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
                    fixed = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
                    analyses = [uuid.uuid4() for _ in range(3)]
                    foreign_analysis = uuid.uuid4()
                    versions = [uuid.uuid4() for _ in range(3)]
                    baseline, baseline_version = uuid.uuid4(), uuid.uuid4()
                    document, document_version, ai_task = (
                        uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                    )
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for number, analysis_id in enumerate(analyses):
                            db.execute(
                                "INSERT INTO plm.hnd_analyses"
                                "(handover_analysis_id,project_id,analysis_purpose,"
                                "source_set_ref,analysis_state,created_by,created_at,"
                                "updated_at,lock_version) VALUES "
                                "(%s,%s,%s,%s,'ACTIVE',%s,%s,%s,0)",
                                (analysis_id, project, f"Purpose {number}",
                                 "sha256:" + str(number) * 64, pm, fixed, fixed),
                            )
                        db.execute(
                            "INSERT INTO plm.hnd_analyses"
                            "(handover_analysis_id,project_id,analysis_purpose,"
                            "source_set_ref,analysis_state,created_by,created_at,"
                            "updated_at,lock_version) VALUES "
                            "(%s,%s,'Foreign',%s,'ACTIVE',%s,%s,%s,0)",
                            (foreign_analysis, foreign_project,
                             "sha256:" + "f" * 64, foreign, fixed, fixed),
                        )
                        for number, version_id in enumerate(versions, 1):
                            db.execute(
                                "INSERT INTO plm.hnd_analysis_versions"
                                "(handover_analysis_version_id,handover_analysis_id,"
                                "project_id,version_no,version_state,source_set_ref,"
                                "capability_baseline_id,capability_baseline_version_ref,"
                                "content_fingerprint,declared_source_count,"
                                "declared_item_count,declared_evidence_count,"
                                "declared_capability_ref_count,declared_ai_task_count,"
                                "created_by,created_at) VALUES "
                                "(%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,1,3,3,3,1,%s,%s)",
                                (version_id, analyses[0], project, number,
                                 "sha256:" + "a" * 64, baseline,
                                 baseline_version, bytes([number]) * 32, pm, fixed),
                            )
                        db.execute(
                            "INSERT INTO plm.hnd_analysis_source_document_refs"
                            "(source_document_ref_id,handover_analysis_version_id,"
                            "handover_analysis_id,project_id,document_id,"
                            "document_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,%s,0)",
                            (uuid.uuid4(), versions[2], analyses[0], project,
                             document, document_version),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_analysis_ai_task_refs"
                            "(ai_task_ref_id,handover_analysis_version_id,"
                            "handover_analysis_id,project_id,ai_task_id,task_scope,ordinal) "
                            "VALUES (%s,%s,%s,%s,%s,'PROJECT',0)",
                            (uuid.uuid4(), versions[2], analyses[0], project, ai_task),
                        )
                        for ordinal in range(3):
                            row_id, item_id = uuid.uuid4(), uuid.uuid4()
                            evidence, capability = uuid.uuid4(), uuid.uuid4()
                            db.execute(
                                "INSERT INTO plm.hnd_analysis_items"
                                "(analysis_item_row_id,handover_analysis_version_id,"
                                "handover_analysis_id,project_id,analysis_item_id,ordinal,"
                                "item_type,title,statement,impact,severity,priority,"
                                "recommendation,confirmation_question,required_input_spec,"
                                "source_missing,item_state) VALUES "
                                "(%s,%s,%s,%s,%s,%s,'NEED_CONFIRM',%s,'Statement',"
                                "'Impact','HIGH','HIGH','Recommendation','Question?',"
                                "'{\"fields\":[{\"name\":\"answer\"}]}'::jsonb,false,'CANDIDATE')",
                                (row_id, versions[2], analyses[0], project, item_id,
                                 ordinal, f"Item {ordinal}"),
                            )
                            db.execute(
                                "INSERT INTO plm.hnd_item_evidence_refs"
                                "(item_evidence_ref_id,analysis_item_row_id,"
                                "handover_analysis_version_id,handover_analysis_id,"
                                "project_id,evidence_id,ordinal) "
                                "VALUES (%s,%s,%s,%s,%s,%s,0)",
                                (uuid.uuid4(), row_id, versions[2], analyses[0],
                                 project, evidence),
                            )
                            db.execute(
                                "INSERT INTO plm.hnd_item_capability_refs"
                                "(item_capability_ref_id,analysis_item_row_id,"
                                "handover_analysis_version_id,handover_analysis_id,"
                                "project_id,baseline_version_id,capability_item_id,ordinal) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,0)",
                                (uuid.uuid4(), row_id, versions[2], analyses[0],
                                 project, baseline_version, capability),
                            )
                            db.execute(
                                "INSERT INTO plm.hnd_item_options"
                                "(item_option_id,analysis_item_row_id,"
                                "handover_analysis_version_id,handover_analysis_id,"
                                "project_id,option_code,label,ordinal) "
                                "VALUES (%s,%s,%s,%s,%s,'A','Option A',0)",
                                (uuid.uuid4(), row_id, versions[2], analyses[0], project),
                            )
                    before = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.hnd_analyses),"
                        "(SELECT count(*) FROM plm.hnd_analysis_versions),"
                        "(SELECT count(*) FROM plm.hnd_analysis_items)"
                    ).fetchone()

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )

                def service(custom_guard=None):
                    return HandoverAnalysisReadService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectReadAccess(),
                        license_guard=custom_guard or guard,
                        authorization=authorization,
                        repository=SqlAlchemyHandoverAnalysisReadRepository(),
                    )

                def query(index: int, selected_project=project):
                    return HandoverAnalysisReadQuery(
                        tokens[index], uuid.uuid4(), selected_project,
                    )

                for index in range(4):
                    first = service().list_analyses(query(index), page_size=2)
                    assert len(first.items) == 2 and first.has_more
                    second = service().list_analyses(
                        query(index), page_size=2,
                        after_updated_at=first.next_updated_at,
                        after_handover_analysis_id=first.next_handover_analysis_id,
                    )
                    assert len(second.items) == 1 and not second.has_more
                    assert len({item.handover_analysis_id
                                for item in first.items + second.items}) == 3
                analysis = service().get_analysis(query(0), analyses[0])
                assert analysis.etag == '"v0"' and analysis.project_id == project
                version_page = service().list_versions(
                    query(0), handover_analysis_id=analyses[0], page_size=2,
                )
                assert [item.version_no for item in version_page.items] == [3, 2]
                version_tail = service().list_versions(
                    query(0), handover_analysis_id=analyses[0], page_size=2,
                    after_version_no=version_page.next_version_no,
                )
                assert [item.version_no for item in version_tail.items] == [1]
                detail = service().get_version(
                    query(0), handover_analysis_id=analyses[0],
                    handover_analysis_version_id=versions[2],
                )
                assert detail.content_fingerprint == (bytes([3]) * 32).hex()
                assert len(detail.source_documents) == 1 and len(detail.ai_tasks) == 1
                first_items = service().list_items(
                    query(0), handover_analysis_id=analyses[0],
                    handover_analysis_version_id=versions[2], page_size=2,
                )
                second_items = service().list_items(
                    query(0), handover_analysis_id=analyses[0],
                    handover_analysis_version_id=versions[2], page_size=2,
                    after_ordinal=first_items.next_ordinal,
                )
                assert [item.ordinal for item in first_items.items] == [0, 1]
                assert [item.ordinal for item in second_items.items] == [2]
                assert all(len(item.evidence_refs) == 1
                           and len(item.capability_refs) == 1
                           and len(item.options) == 1
                           and item.required_input_spec["fields"][0]["name"] == "answer"
                           for item in first_items.items + second_items.items)
                expect("RESOURCE_NOT_FOUND", lambda: service().get_analysis(
                    query(0), foreign_analysis,
                ))
                expect("RESOURCE_NOT_FOUND", lambda: service().list_analyses(
                    query(4), page_size=10,
                ))
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s",
                        (project,),
                    )
                assert len(service().list_analyses(query(0), page_size=10).items) == 3
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s",
                        (project,),
                    )
                    db.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s", (project, customer),
                    )
                expect("RESOURCE_NOT_FOUND", lambda: service().list_analyses(
                    query(3), page_size=10,
                ))
                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(expired).get_analysis(
                    query(0), analyses[0],
                ))
                with connect(name) as db:
                    after = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.hnd_analyses),"
                        "(SELECT count(*) FROM plm.hnd_analysis_versions),"
                        "(SELECT count(*) FROM plm.hnd_analysis_items)"
                    ).fetchone()
                    assert before == after, (before, after)
                print(
                    "HND_01_A05_A02_ANALYSIS_READ_OWNER_PASS: four-role current "
                    "membership, tied-timestamp Analysis keyset, descending Version "
                    "and ascending Item pagination, safe bounded reference projections, "
                    "cross-project/revoked/License denial, archived reads and zero writes "
                    "verified on PostgreSQL 18"
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
