"""Windows 11/PostgreSQL 18 proof for PrototypeTemplate CREATE owner."""

from __future__ import annotations

import runpy
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.prototype.application.create_template import (
    CreateGlobalPrototypeTemplate, CreateProjectPrototypeTemplate,
    PrototypeTemplateCreateError, PrototypeTemplateCreateService,
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.infrastructure.template_create_repository import (
    SqlAlchemyPrototypeTemplateCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261008_0127"


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypeTemplateCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def seed_document(db, *, actor, scope, project_id, name):
    document_id, file_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    digest = (name.encode("utf-8") + b"0" * 32)[:32].ljust(32, b"0")
    locator = "prototype-template/" + uuid.uuid4().hex
    db.execute(
        "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,file_state,"
        "created_by,available_at) VALUES (%s,%s,%s,'PERSISTENT',%s,%s,%s,16,"
        "'application/json','AVAILABLE',%s,statement_timestamp())",
        (file_id, scope, project_id, locator, name + ".json", digest, actor),
    )
    db.execute(
        "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,title,"
        "original_display_name,document_state,created_by) VALUES (%s,%s,%s,'TEMPLATE',%s,%s,"
        "'ACTIVE',%s)",
        (document_id, scope, project_id, name, name + ".json", actor),
    )
    db.execute(
        "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,project_id,"
        "version_no,file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
        "created_by,availability_state,integrity_checked_at) VALUES (%s,%s,%s,%s,1,%s,%s,16,"
        "'application/json','{}'::jsonb,%s,'AVAILABLE',statement_timestamp())",
        (version_id, document_id, scope, project_id, file_id, digest, actor),
    )
    return version_id


def main() -> None:
    database = "prt01a04a03_" + uuid.uuid4().hex[:8]
    admin_token, pm_token = b"a" * 32, b"p" * 32
    impl_token, customer_token = b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            admin_id = seed_user(db, "Template admin", "DEPLOYMENT_ADMIN", admin_token)
            pm = seed_user(db, "Template PM", "NONE", pm_token)
            impl = seed_user(db, "Template IM", "NONE", impl_token)
            customer = seed_user(db, "Template customer", "NONE", customer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTT03','prtt03','Template create project',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            other = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTT04','prtt04','Other template project',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                    "project_role) VALUES (%s,%s,%s,%s)",
                    (project, actor, department, role),
                )
            project_doc = seed_document(
                db, actor=pm, scope="PROJECT", project_id=project,
                name="Project layout",
            )
            global_doc = seed_document(
                db, actor=admin_id, scope="GLOBAL", project_id=None,
                name="Global layout",
            )
            other_doc = seed_document(
                db, actor=pm, scope="PROJECT", project_id=other,
                name="Other layout",
            )

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        common = dict(
            unit_of_work=runtime.unit_of_work,
            project_access=SqlAlchemyProjectWriteAccess(),
            admin_access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
            authorization=authorization,
            document_artifacts=SqlAlchemyPrototypeDocumentArtifactProof(),
            repository=SqlAlchemyPrototypeTemplateCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )

        def service(audit=None):
            return PrototypeTemplateCreateService(
                **common, audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        project_command = CreateProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project, "Review form",
            {"schema": 1, "regions": ["main", "side"]},
            {"schema": 1, "components": ["form", "table"]},
            ("TABLET_WEB", "DESKTOP_WEB"),
            (TemplateArtifactRef("DOCUMENT_VERSION", project_doc),
             TemplateArtifactRef("DOCUMENT_VERSION", global_doc)),
            str(uuid.uuid4()),
        )
        expect(
            "RESOURCE_NOT_FOUND",
            lambda: service().create_project(replace(
                project_command, session_token=customer_token,
            )),
        )
        expect(
            "AUTH_ACCESS_DENIED",
            lambda: service().create_global(CreateGlobalPrototypeTemplate(
                pm_token, CSRF, uuid.uuid4(), "Not admin", {"schema": 1},
                {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
            )),
        )
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: service().create_project(project_command))
        guard.enabled = True
        expect(
            "PROTOTYPE_ARTIFACT_UNAVAILABLE",
            lambda: service().create_project(replace(
                project_command,
                artifact_refs=(TemplateArtifactRef("OUTPUT_ARTIFACT", uuid.uuid4()),),
                idempotency_key=str(uuid.uuid4()),
            )),
        )
        expect(
            "PROTOTYPE_ARTIFACT_UNAVAILABLE",
            lambda: service().create_project(replace(
                project_command,
                artifact_refs=(TemplateArtifactRef("DOCUMENT_VERSION", other_doc),),
                idempotency_key=str(uuid.uuid4()),
            )),
        )
        expect(
            "PROTOTYPE_UNAVAILABLE",
            lambda: service(FailedAudit()).create_project(replace(
                project_command, idempotency_key=str(uuid.uuid4()),
            )),
        )
        created = service().create_project(project_command)
        assert created.scope == "PROJECT" and created.project_id == project
        assert created.version_no == 1 and created.etag == '"v0"'
        assert created.applicable_terminals == ("DESKTOP_WEB", "TABLET_WEB")
        assert created.artifact_refs == tuple(sorted(
            project_command.artifact_refs,
            key=lambda item: (item.artifact_kind, str(item.target_id)),
        ))
        assert service().create_project(project_command) == created
        expect(
            "CONFLICT_IDEMPOTENCY",
            lambda: service().create_project(replace(
                project_command, name="Different replay",
            )),
        )

        global_command = CreateGlobalPrototypeTemplate(
            admin_token, CSRF, uuid.uuid4(), "Global review form",
            {"schema": 1, "regions": ["main"]},
            {"schema": 1, "components": ["form"]},
            ("DESKTOP_WEB",),
            (TemplateArtifactRef("DOCUMENT_VERSION", global_doc),),
            str(uuid.uuid4()),
        )
        global_created = service().create_global(global_command)
        assert global_created.scope == "GLOBAL" and global_created.project_id is None
        assert service().create_global(global_command) == global_created
        expect(
            "PROTOTYPE_ARTIFACT_UNAVAILABLE",
            lambda: service().create_global(replace(
                global_command,
                artifact_refs=(TemplateArtifactRef("DOCUMENT_VERSION", project_doc),),
                idempotency_key=str(uuid.uuid4()),
            )),
        )

        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prt_templates").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.prt_template_versions").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.prt_template_artifact_refs").fetchone()[0] == 3
            assert db.execute("SELECT count(*) FROM plm.prt_template_command_results").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='PROTOTYPE_TEMPLATE_CREATED'"
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation LIKE "
                "'V1_PRT_TEMPLATE_%_CREATE'"
            ).fetchone()[0] == 2
            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,"
                        "template_state,current_template_version_ref,created_by,lock_version) "
                        "VALUES (%s,'PROJECT',%s,'Incomplete','ACTIVE',%s,%s,0)",
                        (uuid.uuid4(), project, uuid.uuid4(), pm),
                    )
            except Exception as error:
                assert (
                    "PrototypeTemplate has no complete first version" in str(error)
                    or "fk_prt_templates__current_version" in str(error)
                ), str(error)
            else:
                raise AssertionError("incomplete Template committed")
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,))
        expect("AUTH_ACCESS_DENIED", lambda: service().create_project(project_command))
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "PrototypeTemplate create history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0128 accepted Template create history")
        print(
            "PRT_01_A04_A03_TEMPLATE_CREATE_PASS: project/global authorization, "
            "license, DocumentVersion proof, OutputArtifact fail-closed, canonical "
            "contracts, replay/conflict, Audit rollback, atomic closure, revoked replay "
            "and history refusal verified on PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )


if __name__ == "__main__":
    main()
