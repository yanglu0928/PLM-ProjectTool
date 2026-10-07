"""Windows 11/PostgreSQL 18 closure for all Requirement fixed source proofs."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.capability.infrastructure.requirement_source_proof import (
    SqlAlchemyCapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import (
    SqlAlchemyEvidenceRequirementSourceProof,
)
from plm_assistant.modules.handover.infrastructure.requirement_source_proof import (
    SqlAlchemyHandoverRequirementSourceProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.requirement.infrastructure.human_decision_source_proof import (
    SqlAlchemyRequirementHumanDecisionSourceProof,
)
from plm_assistant.modules.survey.infrastructure.requirement_source_proof import (
    SqlAlchemySurveyConclusionRequirementSourceProof,
)


ROOT = Path(__file__).resolve().parents[2]
definition = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
rounds = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"
))
upstream = runpy.run_path(str(
    ROOT / "validation" / "req-01-a05-a02-upstream-source-proofs" / "verify.py"
))
connect = definition["connect"]
seed_dependencies = definition["seed_dependencies"]
insert_valid = definition["insert_valid"]
insert_evidence = rounds["insert_evidence"]
project_review = upstream["review_fixture"]


def counts(database: str) -> tuple[int, ...]:
    with connect(database) as db:
        return db.execute(
            "SELECT (SELECT count(*) FROM plm.req_requirement_state_decisions),"
            "(SELECT count(*) FROM plm.req_requirement_decision_evidence_refs),"
            "(SELECT count(*) FROM plm.req_requirement_command_results),"
            "(SELECT count(*) FROM plm.srv_conclusions),"
            "(SELECT count(*) FROM plm.evd_evidence_records),"
            "(SELECT count(*) FROM plm.rvw_subject_snapshots)"
        ).fetchone()


def main() -> None:
    database = "req01a05a04_" + uuid.uuid4().hex[:8]
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
        with connect(database) as db:
            ids = seed_dependencies(db)
            survey, _ = insert_valid(db, ids, name="Requirement closure survey")
            evidence, _, _, _ = insert_evidence(db, ids)
            values = {name: uuid.uuid4() for name in (
                "h_review", "h_round", "h_snapshot", "series", "conclusion",
                "s_review", "s_round", "s_snapshot", "c_review", "c_round",
                "c_snapshot", "requirement", "decision", "result",
            )}
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                project_review(
                    db, review_id=values["h_review"], round_id=values["h_round"],
                    snapshot_id=values["h_snapshot"], project_id=ids["project"],
                    actor_id=ids["actor"], subject_type="HND-02",
                    subject_id=ids["analysis"], version_id=ids["analysis_version"],
                    policy_code="HANDOVER_ALL_V1", fingerprint=b"h" * 32,
                )
                db.execute(
                    "UPDATE plm.hnd_analysis_versions SET review_ref=%s,"
                    "review_round_ref=%s WHERE handover_analysis_version_id=%s",
                    (values["h_review"], values["h_round"], ids["analysis_version"]),
                )
                project_review(
                    db, review_id=values["s_review"], round_id=values["s_round"],
                    snapshot_id=values["s_snapshot"], project_id=ids["project"],
                    actor_id=ids["actor"], subject_type="SRV-05",
                    subject_id=values["series"], version_id=values["conclusion"],
                    policy_code="SURVEY_CONCLUSION_ALL_V1", fingerprint=b"q" * 32,
                )
                db.execute(
                    "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
                    "conclusion_series_id,project_id,survey_id,round_refs,ai_task_refs,"
                    "version_no,conclusion_state,content_fingerprint,"
                    "declared_department_count,declared_module_count,"
                    "declared_evidence_count,declared_open_issue_count,review_ref,"
                    "review_round_ref,created_by) VALUES "
                    "(%s,%s,%s,%s,ARRAY[%s]::uuid[],'{}'::uuid[],1,'APPROVED',%s,"
                    "1,0,1,0,%s,%s,%s)",
                    (values["conclusion"], values["series"], ids["project"],
                     survey, uuid.uuid4(), b"q" * 32, values["s_review"],
                     values["s_round"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,"
                    "subject_type,subject_id,policy_code,review_state,active_round_id,"
                    "lock_version,created_by) VALUES "
                    "(%s,'GLOBAL',NULL,'CAP-01',%s,'DEPLOYMENT_ALL_V1',"
                    "'APPROVED',NULL,2,%s)",
                    (values["c_review"], ids["baseline"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,"
                    "scope,project_id,round_no,subject_version_id,round_state,"
                    "lock_version,started_by,started_at) VALUES "
                    "(%s,%s,'GLOBAL',NULL,1,%s,'APPROVED',1,%s,"
                    "statement_timestamp())",
                    (values["c_round"], values["c_review"],
                     ids["baseline_version"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,"
                    "review_round_id,scope,project_id,subject_type,subject_id,"
                    "subject_version_id,content_fingerprint,proof_schema_version,"
                    "verified_at) VALUES "
                    "(%s,%s,%s,'GLOBAL',NULL,'CAP-01',%s,%s,%s,1,"
                    "statement_timestamp())",
                    (values["c_snapshot"], values["c_review"], values["c_round"],
                     ids["baseline"], ids["baseline_version"], b"c" * 32),
                )
                db.execute(
                    "UPDATE plm.cap_baseline_versions SET review_ref=%s,"
                    "review_round_ref=%s WHERE baseline_version_id=%s",
                    (values["c_review"], values["c_round"],
                     ids["baseline_version"]),
                )
                db.execute(
                    "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                    "requirement_code,requirement_code_normalized,requirement_state,"
                    "created_by,updated_by,lock_version) VALUES "
                    "(%s,%s,'REQ-HUMAN','REQ-HUMAN','DEFERRED',%s,%s,1)",
                    (values["requirement"], ids["project"], ids["actor"],
                     ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_state_decisions(decision_id,"
                    "requirement_id,project_id,decision_type,reason,impact,decided_by,"
                    "before_version,after_version) VALUES "
                    "(%s,%s,%s,'DEFER','Customer deferred scope',"
                    "'Schedule and scope impact',%s,0,1)",
                    (values["decision"], values["requirement"], ids["project"],
                     ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_decision_evidence_refs("
                    "decision_id,requirement_id,project_id,evidence_id) "
                    "VALUES (%s,%s,%s,%s)",
                    (values["decision"], values["requirement"], ids["project"],
                     evidence),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_command_results(result_id,"
                    "requirement_id,project_id,operation,requirement_code,"
                    "requirement_state,decision_id,reason,impact,evidence_refs,"
                    "lock_version) VALUES "
                    "(%s,%s,%s,'DEFER','REQ-HUMAN','DEFERRED',%s,"
                    "'Customer deferred scope','Schedule and scope impact',"
                    "ARRAY[%s]::uuid[],1)",
                    (values["result"], values["requirement"], ids["project"],
                     values["decision"], evidence),
                )

        runtime = create_database_runtime(url)
        proofs = (
            SqlAlchemySurveyConclusionRequirementSourceProof(),
            SqlAlchemyHandoverRequirementSourceProof(),
            SqlAlchemyRequirementHumanDecisionSourceProof(),
            SqlAlchemyEvidenceRequirementSourceProof(),
            SqlAlchemyCapabilityRequirementSourceProof(),
        )
        before = counts(database)
        with runtime.unit_of_work() as tx:
            survey_proof = proofs[0].prove(
                tx, project_id=ids["project"],
                survey_conclusion_id=values["conclusion"],
            )
            handover_proof = proofs[1].prove(
                tx, project_id=ids["project"],
                handover_analysis_id=ids["analysis"],
                handover_analysis_version_id=ids["analysis_version"],
            )
            decision_proof = proofs[2].prove(
                tx, project_id=ids["project"], decision_id=values["decision"],
            )
            evidence_proof = proofs[3].prove(
                tx, project_id=ids["project"], evidence_id=evidence,
            )
            capability_proof = proofs[4].prove(
                tx, baseline_version_id=ids["baseline_version"],
                capability_item_id=ids["capability_item"],
            )
            assert all(item is not None for item in (
                survey_proof, handover_proof, decision_proof,
                evidence_proof, capability_proof,
            ))
            assert decision_proof.decision_type == "DEFER"
            assert decision_proof.evidence_refs == (evidence,)
            assert proofs[2].prove(
                tx, project_id=uuid.uuid4(), decision_id=values["decision"],
            ) is None
            tx.commit()
        assert counts(database) == before

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='A04 current-source revocation' "
                "WHERE evidence_id=%s", (evidence,),
            )
        with runtime.unit_of_work() as tx:
            assert proofs[3].prove(
                tx, project_id=ids["project"], evidence_id=evidence,
            ) is None
            historical = proofs[2].prove(
                tx, project_id=ids["project"], decision_id=values["decision"],
            )
            assert historical is not None and historical.evidence_refs == (evidence,)

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.req_requirement_command_results SET "
                "evidence_refs=ARRAY[%s]::uuid[] WHERE result_id=%s",
                (uuid.uuid4(), values["result"]),
            )
        with runtime.unit_of_work() as tx:
            assert proofs[2].prove(
                tx, project_id=ids["project"], decision_id=values["decision"],
            ) is None
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "REQ_01_A05_A04_FIXED_SOURCE_CLOSURE_PASS: approved Survey, current "
        "Handover, immutable DEFER/REJECT human decision, PROJECT Evidence and "
        "current GLOBAL Capability proofs closed in one caller transaction; "
        "decision-result evidence mismatch, cross-project access, current Evidence "
        "revocation versus immutable decision history and zero writes verified on "
        "Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
