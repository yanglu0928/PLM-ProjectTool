"""Windows 11/PostgreSQL 18 proof for PRT Review lifecycle schema."""

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
from plm_assistant.modules.prototype.application.create_version import (
    VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.infrastructure.version_create_repository import (
    SqlAlchemyPrototypeVersionCreateRepository,
)

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0131"


def main():
    database = "prt01a07p01_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    engine = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head"); command.check(cfg)
        command.downgrade(cfg, PREVIOUS); command.upgrade(cfg, "head"); command.check(cfg)
        with connect(database) as db:
            actor = seed_user(db, "Prototype Review schema actor", "NONE", b"z" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTVREVIEW','prtvreview','Prototype Review project',%s) RETURNING project_id",
                (actor,)).fetchone()[0]
        ids = {name: uuid.uuid4() for name in (
            "prototype", "template", "template_version", "requirement",
            "requirement_version", "document_version")}
        engine = create_engine(url)
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL session_replication_role='replica'"))
            session.execute(text(
                "INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,created_by) "
                "VALUES (:id,:p,'Review prototype',:a)"),
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
                "VALUES (:r,:p,'R-REVIEW','R-REVIEW',:v,:a)"),
                {"r": ids["requirement"], "p": project,
                 "v": ids["requirement_version"], "a": actor})
            session.execute(text(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,"
                "version_no,version_state,statement,rationale,domain_name,priority,risk,requirement_classification,"
                "content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,"
                "declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,"
                "created_by) VALUES (:v,:r,:p,1,'DRAFT','S','R','D','HIGH','LOW','STANDARD_FUNCTION',"
                ":f,1,0,0,0,0,0,0,:a)"),
                {"v": ids["requirement_version"], "r": ids["requirement"], "p": project,
                 "f": b"r" * 32, "a": actor})
        repo = SqlAlchemyPrototypeVersionCreateRepository()
        def create_version():
            with Session(engine) as session, session.begin():
                return repo.create(SimpleNamespace(session=session), result_id=uuid.uuid4(),
                    version_id=uuid.uuid4(), project_id=project, prototype_id=ids["prototype"],
                    template_id=ids["template"], template_version_id=ids["template_version"],
                    artifacts=(VersionArtifactRef("DOCUMENT_VERSION", ids["document_version"]),),
                    requirements=(VersionRequirementRef(ids["requirement"], ids["requirement_version"]),),
                    interaction={"interactions": []}, interaction_fingerprint=b"i" * 32,
                    coverage={"covered": 1}, content_fingerprint=uuid.uuid4().bytes * 2,
                    actor_id=actor)
        def seed_review(version_id, state="IN_REVIEW"):
            review, round_id = uuid.uuid4(), uuid.uuid4()
            with Session(engine) as session, session.begin():
                session.execute(text("SET LOCAL session_replication_role='replica'"))
                session.execute(text(
                    "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,subject_id,policy_code,"
                    "review_state,active_round_id,lock_version,created_by) VALUES "
                    "(:r,'PROJECT',:p,'PRT-03',:subject,'PROTOTYPE_ALL_V1',:state,:round,0,:a)"),
                    {"r": review, "p": project, "subject": ids["prototype"], "state": state,
                     "round": round_id if state == "IN_REVIEW" else None, "a": actor})
                session.execute(text(
                    "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,project_id,round_no,"
                    "subject_version_id,round_state,lock_version,started_by,started_at) VALUES "
                    "(:round,:r,'PROJECT',:p,1,:v,:state,0,:a,statement_timestamp())"),
                    {"round": round_id, "r": review, "p": project, "v": version_id,
                     "state": state, "a": actor})
            return review, round_id
        def start(version_id, review, round_id, expected_lock, previous):
            with Session(engine) as session, session.begin():
                session.execute(text(
                    "UPDATE plm.prt_prototypes SET updated_by=:a,updated_at=statement_timestamp(),"
                    "lock_version=lock_version+1 WHERE prototype_id=:root"),
                    {"a": actor, "root": ids["prototype"]})
                session.execute(text(
                    "UPDATE plm.prt_prototype_versions SET version_state='IN_REVIEW',review_ref=:r,"
                    "review_round_ref=:round WHERE prototype_version_id=:v"),
                    {"r": review, "round": round_id, "v": version_id})
                session.execute(text(
                    "INSERT INTO plm.prt_version_review_state_results(prototype_version_id,prototype_id,"
                    "project_id,review_id,review_round_id,event_type,previous_approved_version_ref,"
                    "current_approved_version_ref,actor_id,expected_lock_version,lock_version) VALUES "
                    "(:v,:root,:p,:r,:round,'START',:previous,:previous,:a,:expected,:after)"),
                    {"v": version_id, "root": ids["prototype"], "p": project, "r": review,
                     "round": round_id, "previous": previous, "a": actor,
                     "expected": expected_lock, "after": expected_lock + 1})
        def terminal(version_id, review, round_id, event, expected_lock, previous):
            target = version_id if event == "APPROVED" else previous
            version_state = "APPROVED" if event == "APPROVED" else "RETURNED"
            with Session(engine) as session, session.begin():
                session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
                if event == "APPROVED" and previous is not None:
                    session.execute(text(
                        "UPDATE plm.prt_prototype_versions SET version_state='SUPERSEDED' "
                        "WHERE prototype_version_id=:v"), {"v": previous})
                session.execute(text(
                    "UPDATE plm.prt_prototype_versions SET version_state=:state "
                    "WHERE prototype_version_id=:v"), {"state": version_state, "v": version_id})
                session.execute(text(
                    "UPDATE plm.prt_prototypes SET current_approved_version_ref=:target,updated_by=:a,"
                    "updated_at=statement_timestamp(),lock_version=lock_version+1 WHERE prototype_id=:root"),
                    {"target": target, "a": actor, "root": ids["prototype"]})
                session.execute(text(
                    "INSERT INTO plm.prt_version_review_state_results(prototype_version_id,prototype_id,"
                    "project_id,review_id,review_round_id,event_type,previous_approved_version_ref,"
                    "current_approved_version_ref,actor_id,expected_lock_version,lock_version) VALUES "
                    "(:v,:root,:p,:r,:round,:event,:previous,:target,:a,:expected,:after)"),
                    {"v": version_id, "root": ids["prototype"], "p": project, "r": review,
                     "round": round_id, "event": event, "previous": previous, "target": target,
                     "a": actor, "expected": expected_lock, "after": expected_lock + 1})
        def finish_review(review, round_id, state):
            with Session(engine) as session, session.begin():
                session.execute(text("SET LOCAL session_replication_role='replica'"))
                session.execute(text(
                    "UPDATE plm.rvw_reviews SET review_state=:s,active_round_id=NULL WHERE review_id=:r"),
                    {"s": state, "r": review})
                session.execute(text(
                    "UPDATE plm.rvw_review_rounds SET round_state=:s WHERE review_round_id=:round"),
                    {"s": state, "round": round_id})

        v1 = create_version(); r1, rr1 = seed_review(v1.prototype_version_id)
        start(v1.prototype_version_id, r1, rr1, 0, None)
        try: create_version()
        except Exception as error: assert "cannot be created during Review" in str(error)
        else: raise AssertionError("Review must fence create")
        finish_review(r1, rr1, "APPROVED")
        terminal(v1.prototype_version_id, r1, rr1, "APPROVED", 1, None)

        v2 = create_version(); r2, rr2 = seed_review(v2.prototype_version_id)
        start(v2.prototype_version_id, r2, rr2, 2, v1.prototype_version_id)
        finish_review(r2, rr2, "APPROVED")
        terminal(v2.prototype_version_id, r2, rr2, "APPROVED", 3, v1.prototype_version_id)

        v3 = create_version(); r3, rr3 = seed_review(v3.prototype_version_id)
        start(v3.prototype_version_id, r3, rr3, 4, v2.prototype_version_id)
        finish_review(r3, rr3, "RETURNED")
        terminal(v3.prototype_version_id, r3, rr3, "RETURNED", 5, v2.prototype_version_id)
        with connect(database) as db:
            pointer, lock = db.execute(
                "SELECT current_approved_version_ref,lock_version FROM plm.prt_prototypes "
                "WHERE prototype_id=%s", (ids["prototype"],)).fetchone()
            assert pointer == v2.prototype_version_id and lock == 6
            states = dict(db.execute(
                "SELECT version_no,version_state FROM plm.prt_prototype_versions "
                "WHERE prototype_id=%s", (ids["prototype"],)).fetchall())
            assert states == {1: "SUPERSEDED", 2: "APPROVED", 3: "RETURNED"}
        try: command.downgrade(cfg, PREVIOUS)
        except RuntimeError as error: assert "Prototype Review history prevents downgrade" in str(error)
        else: raise AssertionError("Review history downgrade must fail")
        command.check(cfg)
        print("PRT_01_A07_A02_P01_REVIEW_LIFECYCLE_SCHEMA_PASS: start/create fence, approval pointer, supersede, returned pointer preservation, drift and history downgrade verified on PostgreSQL 18")
    finally:
        if engine is not None: engine.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))

if __name__ == "__main__": main()
