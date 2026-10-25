"""Windows 11/PostgreSQL 18 proof for Requirement Survey/Handover adapters."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.handover.infrastructure.requirement_source_proof import (
    SqlAlchemyHandoverRequirementSourceProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.survey.infrastructure.requirement_source_proof import (
    SqlAlchemySurveyConclusionRequirementSourceProof,
)


ROOT = Path(__file__).resolve().parents[2]
fixture = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
connect = fixture["connect"]
seed_dependencies = fixture["seed_dependencies"]
insert_valid = fixture["insert_valid"]


def counts(database: str) -> tuple[int, ...]:
    with connect(database) as db:
        return db.execute(
            "SELECT (SELECT count(*) FROM plm.srv_conclusions),"
            "(SELECT count(*) FROM plm.hnd_analyses),"
            "(SELECT count(*) FROM plm.hnd_analysis_versions),"
            "(SELECT count(*) FROM plm.rvw_reviews),"
            "(SELECT count(*) FROM plm.rvw_review_rounds),"
            "(SELECT count(*) FROM plm.rvw_subject_snapshots)"
        ).fetchone()


def review_fixture(
    db, *, review_id, round_id, snapshot_id, project_id, actor_id,
    subject_type, subject_id, version_id, policy_code, fingerprint,
) -> None:
    db.execute(
        "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
        "subject_id,policy_code,review_state,active_round_id,lock_version,created_by) "
        "VALUES (%s,'PROJECT',%s,%s,%s,%s,'APPROVED',NULL,2,%s)",
        (review_id, project_id, subject_type, subject_id, policy_code, actor_id),
    )
    db.execute(
        "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,project_id,"
        "round_no,subject_version_id,round_state,lock_version,started_by,started_at) "
        "VALUES (%s,%s,'PROJECT',%s,1,%s,'APPROVED',1,%s,statement_timestamp())",
        (round_id, review_id, project_id, version_id, actor_id),
    )
    db.execute(
        "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,review_round_id,"
        "scope,project_id,subject_type,subject_id,subject_version_id,"
        "content_fingerprint,proof_schema_version,verified_at) "
        "VALUES (%s,%s,%s,'PROJECT',%s,%s,%s,%s,%s,1,statement_timestamp())",
        (snapshot_id, review_id, round_id, project_id, subject_type,
         subject_id, version_id, fingerprint),
    )


def main() -> None:
    database = "req01a05a02_" + uuid.uuid4().hex[:8]
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
            survey, _ = insert_valid(db, ids, name="Requirement proof survey")
            values = {name: uuid.uuid4() for name in (
                "h_review", "h_round", "h_snapshot", "series", "conclusion",
                "s_review", "s_round", "s_snapshot",
            )}
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                review_fixture(
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
                review_fixture(
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

        before = counts(database)
        runtime = create_database_runtime(url)
        surveys = SqlAlchemySurveyConclusionRequirementSourceProof()
        handovers = SqlAlchemyHandoverRequirementSourceProof()
        with runtime.unit_of_work() as tx:
            survey_proof = surveys.prove(
                tx, project_id=ids["project"],
                survey_conclusion_id=values["conclusion"],
            )
            handover_proof = handovers.prove(
                tx, project_id=ids["project"],
                handover_analysis_id=ids["analysis"],
                handover_analysis_version_id=ids["analysis_version"],
            )
            assert survey_proof is not None
            assert survey_proof.conclusion_series_id == values["series"]
            assert survey_proof.review_id == values["s_review"]
            assert survey_proof.content_fingerprint == b"q" * 32
            assert handover_proof is not None
            assert handover_proof.review_id == values["h_review"]
            assert handover_proof.content_fingerprint == b"h" * 32
            assert surveys.prove(
                tx, project_id=uuid.uuid4(),
                survey_conclusion_id=values["conclusion"],
            ) is None
            assert handovers.prove(
                tx, project_id=ids["project"],
                handover_analysis_id=ids["analysis"],
                handover_analysis_version_id=uuid.uuid4(),
            ) is None
            tx.commit()
        assert counts(database) == before

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE snapshot_id=%s", (b"x" * 32, values["s_snapshot"]),
            )
            db.execute(
                "UPDATE plm.hnd_analyses SET analysis_state='RESTRICTED' "
                "WHERE handover_analysis_id=%s", (ids["analysis"],),
            )
        with runtime.unit_of_work() as tx:
            assert surveys.prove(
                tx, project_id=ids["project"],
                survey_conclusion_id=values["conclusion"],
            ) is None
            assert handovers.prove(
                tx, project_id=ids["project"],
                handover_analysis_id=ids["analysis"],
                handover_analysis_version_id=ids["analysis_version"],
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
        "REQ_01_A05_A02_UPSTREAM_SOURCE_PROOFS_PASS: exact PROJECT Survey "
        "Conclusion and current Handover identities, terminal Review/Round/Snapshot "
        "binding, cross-project/version refusal, fingerprint drift, restricted root "
        "and zero-write proof verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
