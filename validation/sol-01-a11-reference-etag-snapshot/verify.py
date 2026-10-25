"""Win11 disposable PG18 proof of 0150 result backfill and divergent ETag."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
import psycopg
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_revise import create_project_reference_revise_router
from plm_assistant.modules.solution.application.revise_reference_solution import ReferenceReviseService
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_created(**facts) -> None:
    port = facts["port"]
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    root, first = facts["created"].reference_solution_id, facts["created"].reference_version_id
    second = uuid.uuid4()
    command.downgrade(cfg, "20261009_0150")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            row = db.execute(
                "SELECT applicability,source_project_class,deidentification_class,"
                "content_fingerprint,source_fingerprint FROM plm.sol_reference_versions "
                "WHERE reference_version_id=%s", (first,)).fetchone()
            stamp = db.execute(
                "INSERT INTO plm.sol_reference_versions"
                "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
                "applicability,source_project_class,deidentification_class,"
                "content_fingerprint,source_fingerprint,declared_document_count,"
                "declared_evidence_count,supersedes_version_ref,created_by) VALUES "
                "(%s,%s,'PROJECT',%s,2,%s,%s,%s,%s,%s,1,1,%s,%s) RETURNING created_at",
                (second, root, facts["project"], Jsonb(row[0]), *row[1:],
                 first, facts["manager"]),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.sol_reference_document_refs"
                "(reference_version_id,reference_solution_id,scope,document_version_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,1)",
                (second, root, facts["document_version"]))
            db.execute(
                "INSERT INTO plm.sol_reference_evidence_refs"
                "(reference_version_id,reference_solution_id,scope,evidence_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,1)",
                (second, root, facts["evidence"]))
            db.execute(
                "UPDATE plm.sol_reference_solutions SET current_version_ref=%s,"
                "lock_version=lock_version+1 WHERE reference_solution_id=%s", (second, root))
            db.execute(
                "INSERT INTO plm.sol_reference_revise_results"
                "(reference_version_id,reference_solution_id,scope,version_no,"
                "supersedes_version_ref,content_fingerprint,source_fingerprint,created_at) "
                "VALUES (%s,%s,'PROJECT',2,%s,%s,%s,%s)",
                (second, root, first, row[3], row[4], stamp))
        # Simulate unknown/manual lock history and verify 0151 does not guess.
        db.execute("ALTER TABLE plm.sol_reference_solutions "
                   "DISABLE TRIGGER trg_sol_reference_solutions__owner")
        try:
            db.execute("UPDATE plm.sol_reference_solutions SET lock_version=7 "
                       "WHERE reference_solution_id=%s", (root,))
        finally:
            db.execute("ALTER TABLE plm.sol_reference_solutions "
                       "ENABLE TRIGGER trg_sol_reference_solutions__owner")
    try:
        command.upgrade(cfg, "20261009_0151")
    except Exception as error:
        assert "Reference lock history requires audited forward repair" in str(error), str(error)
    else:
        raise AssertionError("0151 guessed an unknown historical lock version")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_reference_solutions "
                   "DISABLE TRIGGER trg_sol_reference_solutions__owner")
        try:
            db.execute("UPDATE plm.sol_reference_solutions SET lock_version=1 "
                       "WHERE reference_solution_id=%s", (root,))
        finally:
            db.execute("ALTER TABLE plm.sol_reference_solutions "
                       "ENABLE TRIGGER trg_sol_reference_solutions__owner")
    command.upgrade(cfg, "20261009_0151")
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT result_lock_version FROM plm.sol_reference_revise_results "
            "WHERE reference_version_id=%s", (second,)).fetchone()[0] == 1
        # Synthetic stand-in for a future independent Eligibility lock bump.
        db.execute("ALTER TABLE plm.sol_reference_solutions "
                   "DISABLE TRIGGER trg_sol_reference_solutions__owner")
        try:
            db.execute("UPDATE plm.sol_reference_solutions SET lock_version=5 "
                       "WHERE reference_solution_id=%s", (root,))
        finally:
            db.execute("ALTER TABLE plm.sol_reference_solutions "
                       "ENABLE TRIGGER trg_sol_reference_solutions__owner")
    runtime, audit = facts["runtime"], facts["audit"]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    revises = ReferenceReviseService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=facts["license_guard"], sources=facts["sources"],
        repository=SqlAlchemyReferenceReviseRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    router = create_project_reference_revise_router(
        sessions=sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
        revises=revises)
    path = f"/api/v1/projects/{facts['project']}/reference-solutions/{root}:revise"
    headers = {"cookie": "plm_session=" + facts["token"].hex(),
               "origin": "https://plm.example.test", "x-csrf-token": facts["csrf"].hex(),
               "if-match": '"v5"', "idempotency-key": "etag-divergent-0001"}
    body = {"document_version_ids": [str(facts["document_version"])],
            "evidence_ids": [str(facts["evidence"])],
            "source_project_class": "PLM", "deidentification_class": "PROJECT_INTERNAL",
            "applicability": {"industry": "synthetic"}}
    with TestClient(create_app(project_reference_revise_router=router),
                    base_url="https://plm.example.test") as client:
        first_response = client.post(path, headers=headers, json=body)
        assert first_response.status_code == 201, first_response.text
        assert first_response.json()["data"]["version_no"] == 3
        assert first_response.headers["etag"] == '"v6"'
        assert client.post(path, headers=headers, json=body).json()["data"] == first_response.json()["data"]
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT version_no,result_lock_version "
                          "FROM plm.sol_reference_revise_results WHERE reference_version_id=%s",
                          (uuid.UUID(first_response.json()["data"]["reference_version_id"]),)
                          ).fetchone() == (3, 6)
    try:
        command.downgrade(cfg, "20261009_0150")
    except RuntimeError as error:
        assert "Reference result lock history prevents downgrade" in str(error)
    else:
        raise AssertionError("0151 dropped result lock history")
    print("SOL_01_A11_REFERENCE_ETAG_SNAPSHOT_PG_PASS")


if __name__ == "__main__":
    fixture.main(on_created=on_created)
