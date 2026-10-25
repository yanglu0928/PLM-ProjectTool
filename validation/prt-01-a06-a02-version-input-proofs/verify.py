"""Windows 11/PostgreSQL 18 proof for PrototypeVersion fixed input adapters."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.prototype.infrastructure.version_input_proofs import (
    SqlAlchemyPrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]


def main() -> None:
    database = "prt01a06a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    engine = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            actor = seed_user(db, "PrototypeVersion input proof actor", "NONE", b"p" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTVPROOF','prtvproof','Version proof project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTVOTHER','prtvother','Other proof project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]

        ids = {name: uuid.uuid4() for name in (
            "requirement", "requirement_version", "review", "round",
            "project_template", "project_template_version",
            "global_template", "global_template_version",
            "project_file", "project_document", "project_document_version",
            "global_file", "global_document", "global_document_version",
        )}
        engine = create_engine(url)
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL session_replication_role='replica'"))
            session.execute(text(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
                "requirement_code_normalized,requirement_state,current_approved_version_ref,created_by) "
                "VALUES (:r,:p,'R-PROOF','R-PROOF','ACTIVE',:v,:a)"
            ), {"r": ids["requirement"], "p": project,
                "v": ids["requirement_version"], "a": actor})
            session.execute(text(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,"
                "version_no,version_state,statement,rationale,domain_name,priority,risk,requirement_classification,"
                "content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,"
                "declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,"
                "review_ref,review_round_ref,created_by) VALUES (:v,:r,:p,1,'APPROVED','Statement','Rationale',"
                "'Domain','HIGH','LOW','STANDARD_FUNCTION',:f,1,0,0,0,0,0,0,:review,:round,:a)"
            ), {"v": ids["requirement_version"], "r": ids["requirement"], "p": project,
                "f": b"r" * 32, "review": ids["review"], "round": ids["round"], "a": actor})
            for scope, prefix, template_project in (
                ("PROJECT", "project", project), ("GLOBAL", "global", None),
            ):
                session.execute(text(
                    "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,template_state,"
                    "current_template_version_ref,created_by) VALUES (:t,:s,:p,:n,'ACTIVE',:v,:a)"
                ), {"t": ids[f"{prefix}_template"], "s": scope, "p": template_project,
                    "n": prefix + " proof template", "v": ids[f"{prefix}_template_version"], "a": actor})
                session.execute(text(
                    "INSERT INTO plm.prt_template_versions(prototype_template_version_id,prototype_template_id,"
                    "scope,project_id,version_no,version_state,content_fingerprint,layout_contract,component_contract,"
                    "applicable_terminals,declared_artifact_count,created_by) VALUES "
                    "(:v,:t,:s,:p,1,'PUBLISHED',:f,'{}','{}',ARRAY['DESKTOP_WEB'],0,:a)"
                ), {"v": ids[f"{prefix}_template_version"], "t": ids[f"{prefix}_template"],
                    "s": scope, "p": template_project, "f": (prefix[0].encode() * 32), "a": actor})
            for scope, prefix, document_project in (
                ("PROJECT", "project", project), ("GLOBAL", "global", None),
            ):
                session.execute(text(
                    "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,file_state,"
                    "available_at,created_by) VALUES (:f,:s,:p,'PERSISTENT',:loc,'proof.pdf',:sha,10,"
                    "'application/pdf','AVAILABLE',statement_timestamp(),:a)"
                ), {"f": ids[f"{prefix}_file"], "s": scope, "p": document_project,
                    "loc": prefix + "/proof.pdf", "sha": b"d" * 32, "a": actor})
                session.execute(text(
                    "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,title,"
                    "original_display_name,document_state,created_by) VALUES "
                    "(:d,:s,:p,'REFERENCE_MATERIAL',:n,'proof.pdf','ACTIVE',:a)"
                ), {"d": ids[f"{prefix}_document"], "s": scope, "p": document_project,
                    "n": prefix + " proof document", "a": actor})
                session.execute(text(
                    "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,project_id,"
                    "version_no,file_object_id,content_sha256,size_bytes,detected_mime,availability_state,created_by) "
                    "VALUES (:v,:d,:s,:p,1,:f,:sha,10,'application/pdf','AVAILABLE',:a)"
                ), {"v": ids[f"{prefix}_document_version"], "d": ids[f"{prefix}_document"],
                    "s": scope, "p": document_project, "f": ids[f"{prefix}_file"],
                    "sha": b"d" * 32, "a": actor})

        requirements = SqlAlchemyPrototypeApprovedRequirementVersionProof()
        templates = SqlAlchemyPrototypeVersionTemplateProof()
        documents = SqlAlchemyPrototypeDocumentArtifactProof()
        with Session(engine) as session, session.begin():
            tx = SimpleNamespace(session=session)
            assert requirements.prove(
                tx, project_id=project, requirement_id=ids["requirement"],
                requirement_version_id=ids["requirement_version"],
            ) is not None
            assert requirements.prove(
                tx, project_id=other_project, requirement_id=ids["requirement"],
                requirement_version_id=ids["requirement_version"],
            ) is None
            for prefix in ("project", "global"):
                assert templates.prove(
                    tx, project_id=project,
                    prototype_template_id=ids[f"{prefix}_template"],
                    prototype_template_version_id=ids[f"{prefix}_template_version"],
                ) is not None
                assert documents.prove_for_prototype_version(
                    tx, project_id=project,
                    document_version_id=ids[f"{prefix}_document_version"],
                ) is not None
            assert templates.prove(
                tx, project_id=other_project,
                prototype_template_id=ids["project_template"],
                prototype_template_version_id=ids["project_template_version"],
            ) is None
            assert documents.prove_for_prototype_version(
                tx, project_id=other_project,
                document_version_id=ids["project_document_version"],
            ) is None

        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL session_replication_role='replica'"))
            session.execute(text(
                "UPDATE plm.req_requirements SET requirement_state='ARCHIVED' WHERE requirement_id=:r"
            ), {"r": ids["requirement"]})
            session.execute(text(
                "UPDATE plm.doc_file_objects SET file_state='RESTRICTED' WHERE file_object_id=:f"
            ), {"f": ids["project_file"]})
        with Session(engine) as session, session.begin():
            tx = SimpleNamespace(session=session)
            assert requirements.prove(
                tx, project_id=project, requirement_id=ids["requirement"],
                requirement_version_id=ids["requirement_version"],
            ) is None
            assert documents.prove_for_prototype_version(
                tx, project_id=project,
                document_version_id=ids["project_document_version"],
            ) is None
        print(
            "PRT_01_A06_A02_VERSION_INPUT_PROOFS_PASS: current Approved Requirement, "
            "GLOBAL/same-project PUBLISHED Template and AVAILABLE Document proofs; cross-project "
            "and inactive/unavailable facts fail closed on PostgreSQL 18"
        )
    finally:
        if engine is not None:
            engine.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)
            ))


if __name__ == "__main__":
    main()
