"""Windows 11/PostgreSQL 18 proof for PrototypeTemplate REVISE owner."""

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
    PrototypeTemplateCreateService, TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseError, PrototypeTemplateReviseService,
    ReviseGlobalPrototypeTemplate, ReviseProjectPrototypeTemplate,
)
from plm_assistant.modules.prototype.infrastructure.template_create_repository import (
    SqlAlchemyPrototypeTemplateCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.template_revise_repository import (
    SqlAlchemyPrototypeTemplateReviseRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypeTemplateReviseError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def seed_document(db, *, actor, scope, project_id, name):
    document_id, file_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    digest = (name.encode("utf-8") + b"0" * 32)[:32].ljust(32, b"0")
    db.execute(
        "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,file_state,"
        "created_by,available_at) VALUES (%s,%s,%s,'PERSISTENT',%s,%s,%s,16,"
        "'application/json','AVAILABLE',%s,statement_timestamp())",
        (file_id, scope, project_id, "template-revise/" + uuid.uuid4().hex,
         name + ".json", digest, actor),
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
    database = "prt01a04a04_" + uuid.uuid4().hex[:8]
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
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            admin_id = seed_user(db, "Revise admin", "DEPLOYMENT_ADMIN", admin_token)
            pm = seed_user(db, "Revise PM", "NONE", pm_token)
            impl = seed_user(db, "Revise IM", "NONE", impl_token)
            customer = seed_user(db, "Revise customer", "NONE", customer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTR04','prtr04','Template revise project',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            other = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTR05','prtr05','Other revise project',%s) RETURNING project_id",
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
                db, actor=pm, scope="PROJECT", project_id=project, name="Project v2",
            )
            global_doc = seed_document(
                db, actor=admin_id, scope="GLOBAL", project_id=None, name="Global v2",
            )
            other_doc = seed_document(
                db, actor=pm, scope="PROJECT", project_id=other, name="Other v2",
            )

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        shared = dict(
            unit_of_work=runtime.unit_of_work,
            project_access=SqlAlchemyProjectWriteAccess(),
            admin_access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
            authorization=authorization,
            document_artifacts=SqlAlchemyPrototypeDocumentArtifactProof(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )
        create_service = PrototypeTemplateCreateService(
            **shared, repository=SqlAlchemyPrototypeTemplateCreateRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )

        def revise_service(audit=None):
            return PrototypeTemplateReviseService(
                **shared, repository=SqlAlchemyPrototypeTemplateReviseRepository(),
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        project_created = create_service.create_project(CreateProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project, "Project template",
            {"schema": 1}, {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        global_created = create_service.create_global(CreateGlobalPrototypeTemplate(
            admin_token, CSRF, uuid.uuid4(), "Global template",
            {"schema": 1}, {"schema": 1}, ("DESKTOP_WEB",), (), str(uuid.uuid4()),
        ))
        project_command = ReviseProjectPrototypeTemplate(
            pm_token, CSRF, uuid.uuid4(), project,
            project_created.prototype_template_id, 0,
            {"schema": 2, "regions": ["main"]},
            {"schema": 2, "components": ["form"]},
            ("TABLET_WEB", "DESKTOP_WEB"),
            (TemplateArtifactRef("DOCUMENT_VERSION", project_doc),
             TemplateArtifactRef("DOCUMENT_VERSION", global_doc)),
            str(uuid.uuid4()),
        )
        expect("RESOURCE_NOT_FOUND", lambda: revise_service().revise_project(replace(
            project_command, session_token=customer_token,
        )))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: revise_service().revise_project(
            project_command
        ))
        guard.enabled = True
        expect("PROTOTYPE_ARTIFACT_UNAVAILABLE", lambda: revise_service().revise_project(
            replace(project_command, artifact_refs=(TemplateArtifactRef(
                "OUTPUT_ARTIFACT", uuid.uuid4(),
            ),), idempotency_key=str(uuid.uuid4()))
        ))
        expect("PROTOTYPE_ARTIFACT_UNAVAILABLE", lambda: revise_service().revise_project(
            replace(project_command, artifact_refs=(TemplateArtifactRef(
                "DOCUMENT_VERSION", other_doc,
            ),), idempotency_key=str(uuid.uuid4()))
        ))
        expect("PROTOTYPE_UNAVAILABLE", lambda: revise_service(FailedAudit()).revise_project(
            replace(project_command, idempotency_key=str(uuid.uuid4()))
        ))
        revised = revise_service().revise_project(project_command)
        assert revised.version_no == 2 and revised.etag == '"v1"'
        assert revised.supersedes_version_id == project_created.prototype_template_version_id
        assert revise_service().revise_project(project_command) == revised
        expect("CONFLICT_IDEMPOTENCY", lambda: revise_service().revise_project(replace(
            project_command, layout_contract={"schema": 99},
        )))
        expect("VERSION_CONFLICT", lambda: revise_service().revise_project(replace(
            project_command, idempotency_key=str(uuid.uuid4()),
        )))
        second = revise_service().revise_project(replace(
            project_command, session_token=impl_token, expected_lock_version=1,
            layout_contract={"schema": 3}, artifact_refs=(),
            idempotency_key=str(uuid.uuid4()),
        ))
        assert second.version_no == 3 and second.etag == '"v2"'

        global_command = ReviseGlobalPrototypeTemplate(
            admin_token, CSRF, uuid.uuid4(), global_created.prototype_template_id, 0,
            {"schema": 2}, {"schema": 2}, ("DESKTOP_WEB",),
            (TemplateArtifactRef("DOCUMENT_VERSION", global_doc),), str(uuid.uuid4()),
        )
        global_revised = revise_service().revise_global(global_command)
        assert global_revised.version_no == 2 and global_revised.etag == '"v1"'
        expect("PROTOTYPE_ARTIFACT_UNAVAILABLE", lambda: revise_service().revise_global(
            replace(global_command, artifact_refs=(TemplateArtifactRef(
                "DOCUMENT_VERSION", project_doc,
            ),), expected_lock_version=1, idempotency_key=str(uuid.uuid4()))
        ))

        with connect(database) as db:
            assert db.execute(
                "SELECT lock_version FROM plm.prt_templates WHERE prototype_template_id=%s",
                (project_created.prototype_template_id,),
            ).fetchone()[0] == 2
            chain = db.execute(
                "SELECT version_no,supersedes_version_id FROM plm.prt_template_versions "
                "WHERE prototype_template_id=%s ORDER BY version_no",
                (project_created.prototype_template_id,),
            ).fetchall()
            assert [row[0] for row in chain] == [1, 2, 3]
            assert chain[1][1] == project_created.prototype_template_version_id
            assert chain[2][1] == revised.prototype_template_version_id
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='PROTOTYPE_TEMPLATE_REVISED'"
            ).fetchone()[0] == 3
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation LIKE 'V1_PRT_TEMPLATE_%_REVISE'"
            ).fetchone()[0] == 3
            try:
                with db.transaction():
                    db.execute(
                        "UPDATE plm.prt_templates SET current_template_version_ref=%s,"
                        "updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 "
                        "WHERE prototype_template_id=%s",
                        (uuid.uuid4(), pm, project_created.prototype_template_id),
                    )
            except Exception as error:
                assert (
                    "PrototypeTemplate has no complete revision version" in str(error)
                    or "fk_prt_templates__current_version" in str(error)
                ), str(error)
            else:
                raise AssertionError("incomplete Template revision committed")
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,))
        expect("AUTH_ACCESS_DENIED", lambda: revise_service().revise_project(project_command))
        try:
            command.downgrade(cfg, "20261008_0128")
        except Exception as error:
            assert "PrototypeTemplate revise history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0129 accepted Template revise history")
        print(
            "PRT_01_A04_A04_TEMPLATE_REVISE_PASS: scoped authorization, license, "
            "artifact proof, immutable v1-v3 chain, strong version, replay/conflict, "
            "Audit rollback, atomic pointer closure, revoked replay and history refusal "
            "verified on PostgreSQL 18"
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
