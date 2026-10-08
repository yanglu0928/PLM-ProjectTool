"""Windows 11/PostgreSQL 18 proof for immutable PrototypeVersion reads."""

from __future__ import annotations
import runpy, uuid
from pathlib import Path
from types import SimpleNamespace
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.prototype.infrastructure.version_read_repository import (
    SqlAlchemyPrototypeVersionReadRepository,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeVersionReadValidationService,
)
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
)

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
seed_document = runpy.run_path(str(
    ROOT / "validation" / "prt-01-a04-a03-template-create" / "verify.py"
))["seed_document"]


def main():
    database = "prt01a06a04_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    engine = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            actor = seed_user(db, "PrototypeVersion read actor", "NONE", b"q" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTVREAD','prtvread','Version read project',%s) RETURNING project_id",
                (actor,)).fetchone()[0]
            document_version = seed_document(
                db, actor=actor, scope="PROJECT", project_id=project,
                name="Prototype version artifact",
            )
            document = db.execute(
                "SELECT document_id FROM plm.doc_document_versions "
                "WHERE document_version_id=%s", (document_version,),
            ).fetchone()[0]
        prototype, template, template_version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        requirement, requirement_version = uuid.uuid4(), uuid.uuid4()
        versions = [uuid.uuid4(), uuid.uuid4()]
        engine = create_engine(url)
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL session_replication_role='replica'"))
            session.execute(text(
                "INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,created_by) "
                "VALUES (:id,:p,'Read prototype',:a)"),
                {"id": prototype, "p": project, "a": actor})
            for number, version_id in enumerate(versions, 1):
                prior = None if number == 1 else versions[number - 2]
                session.execute(text(
                    "INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,project_id,"
                    "version_no,version_state,template_ref,template_version_ref,coverage_summary,content_fingerprint,"
                    "declared_artifact_count,declared_requirement_count,declared_interaction_count,"
                    "supersedes_version_ref,created_by) VALUES (:v,:root,:p,:n,'DRAFT',:t,:tv,CAST(:coverage AS jsonb),"
                    ":f,1,1,1,:prior,:a)"),
                    {"v": version_id, "root": prototype, "p": project, "n": number,
                     "t": template, "tv": template_version, "f": bytes([number]) * 32,
                     "prior": prior, "a": actor, "coverage": '{"covered":1}'})
                session.execute(text(
                    "INSERT INTO plm.prt_version_artifact_refs(prototype_version_id,prototype_id,project_id,"
                    "artifact_kind,target_id,ordinal) VALUES (:v,:root,:p,'DOCUMENT_VERSION',:d,1)"),
                    {"v": version_id, "root": prototype, "p": project, "d": document_version})
                session.execute(text(
                    "INSERT INTO plm.prt_version_requirement_refs(prototype_version_id,prototype_id,project_id,"
                    "requirement_id,requirement_version_id,ordinal) VALUES (:v,:root,:p,:r,:rv,1)"),
                    {"v": version_id, "root": prototype, "p": project,
                     "r": requirement, "rv": requirement_version})
                session.execute(text(
                    "INSERT INTO plm.prt_interaction_specs(prototype_version_id,prototype_id,project_id,"
                    "schema_version,specification,content_fingerprint) VALUES (:v,:root,:p,1,"
                    "CAST(:spec AS jsonb),:f)"),
                    {"v": version_id, "root": prototype, "p": project,
                     "spec": '{"interactions":[]}', "f": b"i" * 32})
        repo = SqlAlchemyPrototypeVersionReadRepository()
        with Session(engine) as session, session.begin():
            tx = SimpleNamespace(session=session)
            page = repo.list(tx, project_id=project, prototype_id=prototype,
                             before_version_no=None, limit=10)
            assert [x.version_no for x in page] == [2, 1]
            assert page[0].supersedes_version_id == versions[0]
            assert len(page[0].artifact_refs) == len(page[0].requirement_refs) == 1
            assert page[0].interaction_spec == {"interactions": []}
            assert repo.list(tx, project_id=project, prototype_id=prototype,
                             before_version_no=2, limit=10)[0].version_no == 1
            assert repo.get(tx, project_id=uuid.uuid4(), prototype_id=prototype,
                            version_id=versions[0]) is None
            locator = PrototypeVersionReadValidationService(
                unit_of_work=object(), project_access=object(),
                license_guard=object(), authorization=object(), repository=repo,
                templates=object(), requirements=object(),
                documents=SqlAlchemyPrototypeDocumentArtifactProof(),
                audit_source=object(), receipts=object(), audit=object(),
            )
            located = locator._located(tx, project, page[0])
            assert located.artifact_refs[0].target_id == document_version
            assert located.artifact_refs[0].document_id == document
        print("PRT_01_A06_A04_VERSION_READ_VALIDATE_PASS: immutable descending page, fixed owned-set reconstruction, historical read and project isolation verified on PostgreSQL 18")
    finally:
        if engine is not None: engine.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__": main()
