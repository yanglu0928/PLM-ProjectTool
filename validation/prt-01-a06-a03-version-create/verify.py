"""Windows 11/PostgreSQL 18 proof for atomic DRAFT PrototypeVersion create."""

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

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.prototype.application.create_version import (
    VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.infrastructure.version_create_repository import (
    SqlAlchemyPrototypeVersionCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0130"


def main() -> None:
    database = "prt01a06a03_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    engine = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS); command.upgrade(cfg, "head"); command.check(cfg)
        command.downgrade(cfg, PREVIOUS); command.upgrade(cfg, "head"); command.check(cfg)
        with connect(database) as db:
            actor = seed_user(db, "PrototypeVersion create actor", "NONE", b"c" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTVCREATE','prtcreate','Version create project',%s) RETURNING project_id",
                (actor,)).fetchone()[0]
        ids = {name: uuid.uuid4() for name in (
            "prototype", "template", "template_version", "requirement",
            "requirement_version", "review", "round", "document_version",
        )}
        engine = create_engine(url)
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL session_replication_role='replica'"))
            session.execute(text(
                "INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,created_by) "
                "VALUES (:id,:p,'Version create prototype',:a)"),
                {"id": ids["prototype"], "p": project, "a": actor})
            session.execute(text(
                "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,"
                "current_template_version_ref,created_by) VALUES (:t,'PROJECT',:p,'Template',:v,:a)"),
                {"t": ids["template"], "p": project, "v": ids["template_version"], "a": actor})
            session.execute(text(
                "INSERT INTO plm.prt_template_versions(prototype_template_version_id,prototype_template_id,"
                "scope,project_id,version_no,content_fingerprint,layout_contract,component_contract,"
                "applicable_terminals,declared_artifact_count,created_by) VALUES "
                "(:v,:t,'PROJECT',:p,1,:f,'{}','{}',ARRAY['DESKTOP_WEB'],0,:a)"),
                {"v": ids["template_version"], "t": ids["template"], "p": project,
                 "f": b"t" * 32, "a": actor})
            session.execute(text(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
                "requirement_code_normalized,current_approved_version_ref,created_by) "
                "VALUES (:r,:p,'R-CREATE','R-CREATE',:v,:a)"),
                {"r": ids["requirement"], "p": project,
                 "v": ids["requirement_version"], "a": actor})
            session.execute(text(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,"
                "version_no,version_state,statement,rationale,domain_name,priority,risk,requirement_classification,"
                "content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,"
                "declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,"
                "review_ref,review_round_ref,created_by) VALUES (:v,:r,:p,1,'APPROVED','S','R','D','HIGH','LOW',"
                "'STANDARD_FUNCTION',:f,1,0,0,0,0,0,0,:review,:round,:a)"),
                {"v": ids["requirement_version"], "r": ids["requirement"], "p": project,
                 "f": b"r" * 32, "review": ids["review"], "round": ids["round"], "a": actor})
        repo = SqlAlchemyPrototypeVersionCreateRepository()
        views = []
        for index in (1, 2):
            with Session(engine) as session, session.begin():
                view = repo.create(
                    SimpleNamespace(session=session), result_id=uuid.uuid4(),
                    version_id=uuid.uuid4(), project_id=project,
                    prototype_id=ids["prototype"], template_id=ids["template"],
                    template_version_id=ids["template_version"],
                    artifacts=(VersionArtifactRef("DOCUMENT_VERSION", ids["document_version"]),),
                    requirements=(VersionRequirementRef(ids["requirement"], ids["requirement_version"]),),
                    interaction={"interactions": []}, interaction_fingerprint=b"i" * 32,
                    coverage={"covered": 1}, content_fingerprint=bytes([index]) * 32,
                    actor_id=actor)
                views.append(view)
        assert views[0].version_no == 1 and views[0].supersedes_version_id is None
        assert views[1].version_no == 2
        assert views[1].supersedes_version_id == views[0].prototype_version_id
        with connect(database) as db:
            assert db.execute(
                "SELECT current_approved_version_ref FROM plm.prt_prototypes WHERE prototype_id=%s",
                (ids["prototype"],)).fetchone()[0] is None
            assert db.execute("SELECT count(*) FROM plm.prt_version_create_results").fetchone()[0] == 2
        try:
            command.downgrade(cfg, PREVIOUS)
        except RuntimeError as error:
            assert "PrototypeVersion create history prevents downgrade" in str(error)
        else:
            raise AssertionError("history downgrade must fail")
        command.check(cfg)
        print(
            "PRT_01_A06_A03_VERSION_CREATE_PASS: empty upgrade/down/re-upgrade, DRAFT v1-v2 chain, "
            "owned-set/result closure, approved pointer isolation, drift and history downgrade refusal "
            "verified on PostgreSQL 18"
        )
    finally:
        if engine is not None: engine.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__": main()
