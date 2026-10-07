"""Windows 11/PostgreSQL 18 proof for Requirement Evidence/Capability adapters."""

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
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
definition = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
rounds = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"
))
connect = definition["connect"]
seed_dependencies = definition["seed_dependencies"]
insert_evidence = rounds["insert_evidence"]


def counts(database: str) -> tuple[int, ...]:
    with connect(database) as db:
        return db.execute(
            "SELECT (SELECT count(*) FROM plm.evd_evidence_records),"
            "(SELECT count(*) FROM plm.cap_baselines),"
            "(SELECT count(*) FROM plm.cap_baseline_versions),"
            "(SELECT count(*) FROM plm.cap_items),"
            "(SELECT count(*) FROM plm.rvw_reviews),"
            "(SELECT count(*) FROM plm.rvw_review_rounds),"
            "(SELECT count(*) FROM plm.rvw_subject_snapshots)"
        ).fetchone()


def main() -> None:
    database = "req01a05a03_" + uuid.uuid4().hex[:8]
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
            evidence, document, document_version, fingerprint = insert_evidence(
                db, ids,
            )
            review, round_id, snapshot = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,"
                    "subject_type,subject_id,policy_code,review_state,active_round_id,"
                    "lock_version,created_by) VALUES "
                    "(%s,'GLOBAL',NULL,'CAP-01',%s,'DEPLOYMENT_ALL_V1',"
                    "'APPROVED',NULL,2,%s)",
                    (review, ids["baseline"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,"
                    "scope,project_id,round_no,subject_version_id,round_state,"
                    "lock_version,started_by,started_at) VALUES "
                    "(%s,%s,'GLOBAL',NULL,1,%s,'APPROVED',1,%s,"
                    "statement_timestamp())",
                    (round_id, review, ids["baseline_version"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,"
                    "review_round_id,scope,project_id,subject_type,subject_id,"
                    "subject_version_id,content_fingerprint,proof_schema_version,"
                    "verified_at) VALUES "
                    "(%s,%s,%s,'GLOBAL',NULL,'CAP-01',%s,%s,%s,1,"
                    "statement_timestamp())",
                    (snapshot, review, round_id, ids["baseline"],
                     ids["baseline_version"], b"c" * 32),
                )
                db.execute(
                    "UPDATE plm.cap_baseline_versions SET review_ref=%s,"
                    "review_round_ref=%s WHERE baseline_version_id=%s",
                    (review, round_id, ids["baseline_version"]),
                )

        before = counts(database)
        runtime = create_database_runtime(url)
        evidences = SqlAlchemyEvidenceRequirementSourceProof()
        capabilities = SqlAlchemyCapabilityRequirementSourceProof()
        with runtime.unit_of_work() as tx:
            evidence_proof = evidences.prove(
                tx, project_id=ids["project"], evidence_id=evidence,
            )
            capability_proof = capabilities.prove(
                tx, baseline_version_id=ids["baseline_version"],
                capability_item_id=ids["capability_item"],
            )
            assert evidence_proof is not None
            assert evidence_proof.document_id == document
            assert evidence_proof.document_version_id == document_version
            assert evidence_proof.content_fingerprint == fingerprint
            assert capability_proof is not None
            assert capability_proof.baseline_id == ids["baseline"]
            assert capability_proof.capability_item_row_id == ids["capability_item_row"]
            assert capability_proof.review_id == review
            assert capability_proof.content_fingerprint == b"c" * 32
            assert evidences.prove(
                tx, project_id=uuid.uuid4(), evidence_id=evidence,
            ) is None
            assert capabilities.prove(
                tx, baseline_version_id=ids["baseline_version"],
                capability_item_id=uuid.uuid4(),
            ) is None
            tx.commit()
        assert counts(database) == before

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='A03 stale-state proof' WHERE evidence_id=%s",
                (evidence,),
            )
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE snapshot_id=%s", (b"x" * 32, snapshot),
            )
        with runtime.unit_of_work() as tx:
            assert evidences.prove(
                tx, project_id=ids["project"], evidence_id=evidence,
            ) is None
            assert capabilities.prove(
                tx, baseline_version_id=ids["baseline_version"],
                capability_item_id=ids["capability_item"],
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
        "REQ_01_A05_A03_REFERENCE_SOURCE_PROOFS_PASS: exact PROJECT/ELIGIBLE "
        "Evidence and current GLOBAL Capability item with terminal Review Snapshot, "
        "cross-project/item refusal, Evidence revocation, fingerprint drift and "
        "zero-write proof verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
