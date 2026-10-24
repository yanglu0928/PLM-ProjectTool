"""Windows 11 disposable PG18 proof for SOL-06 insert-only closure 0164."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol05_owner_for_sol06_guard", ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def rejects(expected: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), (expected, str(error))
    else:
        raise AssertionError("expected " + expected)


def on_created(*, port, project, manager, requirement,
               requirement_version, section, evidence, **_unused) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.check(cfg)  # base fixture upgraded from empty DB to 0164
    command.downgrade(cfg, "20261012_0163")  # empty SOL-06, existing project/history
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_structured_specs").fetchone()[0] == 0
        version_section = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC LIMIT 1",
            (section,)).fetchone()[0]

    series = uuid.uuid4()

    def insert_set(version_id: uuid.UUID, version_no: int,
                   supersedes: uuid.UUID | None, *, req_ordinal: int = 1,
                   section_ordinal: int = 1, evidence_ordinal: int = 1,
                   omit_payload: bool = False, artifact: bool = False) -> None:
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.sol_structured_specs("
                    "structured_solution_spec_id,spec_series_id,project_id,spec_type,"
                    "version_no,content_fingerprint,supersedes_version_ref,created_by) "
                    "VALUES (%s,%s,%s,'MIGRATION_SPEC',%s,%s,%s,%s)",
                    (version_id, series, project, version_no,
                     b"r" * 32, supersedes, manager))
                if not omit_payload:
                    db.execute(
                        "INSERT INTO plm.sol_spec_payloads("
                        "structured_solution_spec_id,spec_series_id,project_id,spec_type,"
                        "payload_json,payload_fingerprint) "
                        "VALUES (%s,%s,%s,'MIGRATION_SPEC',%s::jsonb,%s)",
                        (version_id, series, project, '{"scope":"synthetic"}', b"p" * 32))
                db.execute(
                    "INSERT INTO plm.sol_spec_requirement_refs("
                    "structured_solution_spec_id,spec_series_id,project_id,"
                    "requirement_id,requirement_version_id,ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (version_id, series, project, requirement,
                     requirement_version, req_ordinal))
                db.execute(
                    "INSERT INTO plm.sol_spec_section_refs("
                    "structured_solution_spec_id,spec_series_id,project_id,"
                    "solution_section_id,solution_section_version_id,ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (version_id, series, project, section,
                     version_section, section_ordinal))
                db.execute(
                    "INSERT INTO plm.sol_spec_evidence_refs("
                    "structured_solution_spec_id,spec_series_id,project_id,"
                    "evidence_id,ordinal) VALUES (%s,%s,%s,%s,%s)",
                    (version_id, series, project, evidence, evidence_ordinal))
                if artifact:
                    db.execute(
                        "INSERT INTO plm.sol_spec_artifact_refs("
                        "structured_solution_spec_id,spec_series_id,project_id,"
                        "output_artifact_id,ordinal) VALUES (%s,%s,%s,%s,1)",
                        (version_id, series, project, uuid.uuid4()))

    rejects("draft collection is incomplete", lambda: insert_set(
        uuid.uuid4(), 1, None, omit_payload=True))
    rejects("draft collection is incomplete", lambda: insert_set(
        uuid.uuid4(), 1, None, req_ordinal=2))
    rejects("draft collection is incomplete", lambda: insert_set(
        uuid.uuid4(), 1, None, section_ordinal=2))
    rejects("draft collection is incomplete", lambda: insert_set(
        uuid.uuid4(), 1, None, evidence_ordinal=2))
    rejects("OutputArtifact Owner is not installed", lambda: insert_set(
        uuid.uuid4(), 1, None, artifact=True))
    rejects("version chain is invalid", lambda: insert_set(
        uuid.uuid4(), 2, None))

    first = uuid.uuid4()
    insert_set(first, 1, None)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_requirement_refs "
            "WHERE structured_solution_spec_id=%s", (first,)).fetchone()[0] == 1
        rejects("history is immutable", lambda: db.execute(
            "UPDATE plm.sol_structured_specs SET version_state='APPROVED' "
            "WHERE structured_solution_spec_id=%s", (first,)))
        rejects("history is immutable", lambda: db.execute(
            "DELETE FROM plm.sol_spec_payloads WHERE structured_solution_spec_id=%s",
            (first,)))
        rejects("history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_spec_evidence_refs"))
        rejects("draft collection is sealed", lambda: db.execute(
            "INSERT INTO plm.sol_spec_evidence_refs("
            "structured_solution_spec_id,spec_series_id,project_id,evidence_id,ordinal) "
            "VALUES (%s,%s,%s,%s,2)", (first, series, project, evidence)))
        rejects("draft collection is sealed", lambda: db.execute(
            "INSERT INTO plm.sol_spec_payloads("
            "structured_solution_spec_id,spec_series_id,project_id,spec_type,"
            "payload_json,payload_fingerprint) "
            "VALUES (%s,%s,%s,'MIGRATION_SPEC',%s::jsonb,%s)",
            (first, series, project, '{"scope":"late"}', b"p" * 32)))
    rejects("version chain is invalid", lambda: insert_set(
        uuid.uuid4(), 2, uuid.uuid4()))

    candidates = (uuid.uuid4(), uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(insert_set, candidate, 2, first)
                   for candidate in candidates]
        outcomes = []
        for future in futures:
            try:
                future.result()
                outcomes.append("PASS")
            except Exception as error:
                assert ("version chain is invalid" in str(error)
                        or "uq_sol_specs__series_no" in str(error)), str(error)
                outcomes.append("REJECTED")
    assert sorted(outcomes) == ["PASS", "REJECTED"], outcomes
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_structured_specs WHERE spec_series_id=%s",
            (series,)).fetchone()[0] == 2
    rejects("history prevents guard downgrade", lambda: command.downgrade(
        cfg, "20261012_0163"))
    command.check(cfg)
    print("SOL_06_A09_P01_INSERT_CLOSURE_PG_PASS: empty/existing upgrade, "
          "empty downgrade/re-upgrade, complete set, missing/gap/artifact/"
          "immutability/sealed-collection/chain negatives, concurrent same-series fence, "
          "nonempty downgrade refusal, drift")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_created))
