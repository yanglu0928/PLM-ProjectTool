"""Windows 11/PostgreSQL 18 proof for PrototypeTemplate read owner."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import SqlAlchemyPrototypeDocumentArtifactProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.prototype.application.create_template import (
    CreateGlobalPrototypeTemplate, CreateProjectPrototypeTemplate,
    PrototypeTemplateCreateService, TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.read_templates import (
    GlobalPrototypeTemplateReadQuery, ProjectPrototypeTemplateReadQuery,
    PrototypeTemplateReadError, PrototypeTemplateReadService,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseService, ReviseProjectPrototypeTemplate,
)
from plm_assistant.modules.prototype.infrastructure.template_create_repository import SqlAlchemyPrototypeTemplateCreateRepository
from plm_assistant.modules.prototype.infrastructure.template_read_repository import SqlAlchemyPrototypeTemplateReadRepository
from plm_assistant.modules.prototype.infrastructure.template_revise_repository import SqlAlchemyPrototypeTemplateReviseRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
seed_document = runpy.run_path(str(
    ROOT / "validation" / "prt-01-a04-a03-template-create" / "verify.py"
))["seed_document"]


def expect(code, action):
    try:
        action()
    except PrototypeTemplateReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "prt01a04a05_" + uuid.uuid4().hex[:8]
    admin_token, pm_token = b"a" * 32, b"p" * 32
    member_token, outsider_token, other_token = b"m" * 32, b"o" * 32, b"x" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head"); command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            admin_id = seed_user(db, "Read admin", "DEPLOYMENT_ADMIN", admin_token)
            pm = seed_user(db, "Read PM", "NONE", pm_token)
            member = seed_user(db, "Read member", "NONE", member_token)
            seed_user(db, "Read outsider", "NONE", outsider_token)
            other_pm = seed_user(db, "Other PM", "NONE", other_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTRD1','prtrd1','Read project',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            other = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTRD2','prtrd2','Other project',%s) RETURNING project_id", (other_pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                "VALUES (%s,'BUS','bus','Business') RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in ((pm, "PROJECT_MANAGER"), (member, "CUSTOMER_MEMBER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)", (project, actor, department, role),
                )
            other_department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                "VALUES (%s,'BUS','bus','Business') RETURNING department_id", (other,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (other, other_pm, other_department),
            )
            document_version = seed_document(
                db, actor=pm, scope="PROJECT", project_id=project,
                name="Read project layout",
            )
            document = db.execute(
                "SELECT document_id FROM plm.doc_document_versions "
                "WHERE document_version_id=%s", (document_version,),
            ).fetchone()[0]

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        write_common = dict(
            unit_of_work=runtime.unit_of_work,
            project_access=SqlAlchemyProjectWriteAccess(),
            admin_access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
            authorization=authorization,
            document_artifacts=SqlAlchemyPrototypeDocumentArtifactProof(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            clock=lambda: datetime.now(timezone.utc),
        )
        create = PrototypeTemplateCreateService(
            **write_common, repository=SqlAlchemyPrototypeTemplateCreateRepository(),
        )
        project_one = create.create_project(CreateProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project, "Project one", {"schema": 1},
            {"schema": 1}, ("DESKTOP_WEB",),
            (TemplateArtifactRef("DOCUMENT_VERSION", document_version),),
            str(uuid.uuid4()),
        ))
        project_two = create.create_project(CreateProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project, "Project two", {"schema": 1},
            {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        other_template = create.create_project(CreateProjectPrototypeTemplate(
            other_token, CSRF, uuid.uuid4(), other, "Other", {"schema": 1},
            {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        global_template = create.create_global(CreateGlobalPrototypeTemplate(
            admin_token, CSRF, uuid.uuid4(), "Global", {"schema": 1},
            {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        revise = PrototypeTemplateReviseService(
            **write_common, repository=SqlAlchemyPrototypeTemplateReviseRepository(),
        )
        revised = revise.revise_project(ReviseProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project,
            project_one.prototype_template_id, 0, {"schema": 2}, {"schema": 2},
            ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        reads = PrototypeTemplateReadService(
            unit_of_work=runtime.unit_of_work,
            project_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
            authorization=authorization,
            repository=SqlAlchemyPrototypeTemplateReadRepository(),
            documents=SqlAlchemyPrototypeDocumentArtifactProof(),
            clock=lambda: datetime.now(timezone.utc),
        )
        project_query = ProjectPrototypeTemplateReadQuery(member_token, uuid.uuid4(), project)
        seen = []
        after_at = after_id = None
        while True:
            page = reads.list_project(
                project_query, page_size=1, after_updated_at=after_at,
                after_template_id=after_id,
            )
            seen.extend(item.prototype_template_id for item in page.items)
            if not page.has_more:
                break
            after_at, after_id = page.next_updated_at, page.next_template_id
        assert len(seen) == len(set(seen)) == 3
        assert set(seen) == {
            project_one.prototype_template_id, project_two.prototype_template_id,
            global_template.prototype_template_id,
        }
        current = reads.get_project_version(
            project_query, template_id=project_one.prototype_template_id,
            version_id=revised.prototype_template_version_id,
        )
        historical = reads.get_project_version(
            project_query, template_id=project_one.prototype_template_id,
            version_id=project_one.prototype_template_version_id,
        )
        assert current.is_current and current.version_no == 2 and current.etag == '"v1"'
        assert not historical.is_current and historical.version_no == 1
        assert historical.artifact_refs[0].target_id == document_version
        assert historical.artifact_refs[0].document_id == document
        allowed_global = reads.get_project_version(
            project_query, template_id=global_template.prototype_template_id,
            version_id=global_template.prototype_template_version_id,
        )
        assert allowed_global.scope == "GLOBAL"
        expect("RESOURCE_NOT_FOUND", lambda: reads.get_project_version(
            project_query, template_id=other_template.prototype_template_id,
            version_id=other_template.prototype_template_version_id,
        ))
        global_query = GlobalPrototypeTemplateReadQuery(admin_token, uuid.uuid4())
        global_page = reads.list_global(global_query, page_size=20)
        assert tuple(item.prototype_template_id for item in global_page.items) == (
            global_template.prototype_template_id,
        )
        expect("RESOURCE_NOT_FOUND", lambda: reads.get_global_version(
            global_query, template_id=project_one.prototype_template_id,
            version_id=project_one.prototype_template_version_id,
        ))
        expect("AUTH_ACCESS_DENIED", lambda: reads.list_global(
            GlobalPrototypeTemplateReadQuery(member_token, uuid.uuid4()), page_size=20,
        ))
        expect("RESOURCE_NOT_FOUND", lambda: reads.list_project(
            ProjectPrototypeTemplateReadQuery(outsider_token, uuid.uuid4(), project),
            page_size=20,
        ))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: reads.list_project(project_query, page_size=20))
        guard.enabled = True
        with connect(database) as db:
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (member,))
        expect("AUTH_ACCESS_DENIED", lambda: reads.list_project(project_query, page_size=20))
        print(
            "PRT_01_A04_A05_TEMPLATE_READ_PASS: project PROJECT+GLOBAL visibility, "
            "global admin isolation, stable keyset pagination, current/historical immutable "
            "versions, license and revoked-session fail-closed verified on PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
