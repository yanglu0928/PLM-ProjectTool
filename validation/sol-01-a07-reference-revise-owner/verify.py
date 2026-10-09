"""Disposable Win11 PG18 proof for authorized PROJECT Reference revision."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg
from alembic import command as alembic_command
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseError, ReferenceReviseService, ReviseReferenceSolution,
)
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import (
    SqlAlchemyReferenceReviseRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def denied(action, *codes: str) -> None:
    try:
        action()
    except ReferenceReviseError as error:
        assert error.code in codes, error.code
    else:
        raise AssertionError("Reference revision was accepted")


def sql_denied(action) -> None:
    try:
        action()
    except psycopg.Error:
        pass
    else:
        raise AssertionError("direct SQL bypassed Reference revision guard")


def on_created(**facts) -> None:
    auth = ProjectAuthorizationService(
        unit_of_work=facts["runtime"].unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())

    def service(audit=None, license_guard=None):
        return ReferenceReviseService(
            unit_of_work=facts["runtime"].unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=auth,
            license_guard=license_guard or facts["license_guard"],
            sources=facts["sources"], repository=SqlAlchemyReferenceReviseRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit or facts["audit"],
        )

    from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
    request = ReferenceSourceRequest(
        facts["token"], uuid.uuid4(), "PROJECT", facts["project"],
        (facts["document_version"],), (facts["evidence"],),
        "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
    )
    original = facts["created"]
    command = ReviseReferenceSolution(
        request, facts["csrf"], original.reference_solution_id, 0, "r" * 16)

    class DeniedLicense:
        def require_valid(self, *, trace_id):
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")

    denied(lambda: service(license_guard=DeniedLicense()).revise(command),
           "LICENSE_OPERATION_DENIED")
    denied(lambda: service().revise(replace(
        command, sources=replace(request, project_id=facts["other_project"]))),
        "RESOURCE_NOT_FOUND")
    denied(lambda: service().revise(replace(
        command, sources=replace(request, session_token=b"u" * 32),
        csrf_token=b"v" * 32)), "RESOURCE_NOT_FOUND")
    denied(lambda: service().revise(replace(command, csrf_token=b"x" * 32)),
           "AUTH_ACCESS_DENIED")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service().revise, command)
        second = pool.submit(service().revise, command)
        revised = first.result(timeout=20)
        assert second.result(timeout=20) == revised
    assert revised.version_no == 2
    assert revised.supersedes_version_ref == original.reference_version_id
    assert service().revise(replace(
        command, sources=replace(request, trace_id=uuid.uuid4()))) == revised
    denied(lambda: service().revise(replace(command, idempotency_key="s" * 16)),
           "VERSION_CONFLICT")

    member_request = replace(request, session_token=facts["member_token"],
                             trace_id=uuid.uuid4(), evidence_ids=())
    member_command = ReviseReferenceSolution(
        member_request, facts["member_csrf"], original.reference_solution_id,
        1, "m" * 16)
    third = service().revise(member_command)
    assert third.version_no == 3 and third.supersedes_version_ref == revised.reference_version_id
    assert service().revise(replace(
        command, sources=replace(request, trace_id=uuid.uuid4()))) == revised

    race_base = replace(command, reference_solution_id=facts["member_created"].reference_solution_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service().revise, replace(race_base, idempotency_key="d" * 16))
        second = pool.submit(service().revise, replace(race_base, idempotency_key="e" * 16))
        outcomes = []
        for future in (first, second):
            try:
                outcomes.append(future.result(timeout=20).version_no)
            except ReferenceReviseError as error:
                outcomes.append(error.code)
    assert sorted(outcomes, key=str) == sorted([2, "VERSION_CONFLICT"], key=str), outcomes

    class BrokenAudit:
        def append(self, *_):
            raise RuntimeError("synthetic audit failure")

    denied(lambda: service(BrokenAudit()).revise(replace(
        command, expected_lock_version=2, idempotency_key="b" * 16)),
        "SOLUTION_UNAVAILABLE")
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        root = original.reference_solution_id
        assert db.execute(
            "SELECT current_version_ref,lock_version,eligibility_state "
            "FROM plm.sol_reference_solutions WHERE reference_solution_id=%s",
            (root,)).fetchone() == (third.reference_version_id, 2, "REFERENCE_ONLY")
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_revise_results "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_REVISED' "
            "AND target_object_id=%s", (root,)).fetchone()[0] == 2
        sql_denied(lambda: db.execute(
            "UPDATE plm.sol_reference_solutions SET name='Changed' "
            "WHERE reference_solution_id=%s", (root,)))
        sql_denied(lambda: db.execute(
            "UPDATE plm.sol_reference_versions SET version_no=99 "
            "WHERE reference_version_id=%s", (third.reference_version_id,)))
        sql_denied(lambda: db.execute(
            "DELETE FROM plm.sol_reference_revise_results "
            "WHERE reference_version_id=%s", (third.reference_version_id,)))
        sql_denied(lambda: db.execute("TRUNCATE plm.sol_reference_revise_results"))
        sql_denied(lambda: db.execute(
            "UPDATE plm.sol_reference_solutions SET current_version_ref=%s,"
            "lock_version=lock_version+1 WHERE reference_solution_id=%s",
            (original.reference_version_id, root)))
        sql_denied(lambda: db.execute(
            "INSERT INTO plm.sol_reference_revise_results"
            "(reference_version_id,reference_solution_id,scope,version_no,"
            "supersedes_version_ref,content_fingerprint,source_fingerprint,created_at) "
            "VALUES (%s,%s,'PROJECT',3,%s,%s,%s,now())",
            (third.reference_version_id, root, revised.reference_version_id,
             b"x" * 32, third.source_fingerprint)))

        def incomplete_revision():
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.sol_reference_versions"
                    "(reference_solution_id,scope,project_id,version_no,applicability,"
                    "source_project_class,deidentification_class,content_fingerprint,"
                    "source_fingerprint,declared_document_count,declared_evidence_count,"
                    "supersedes_version_ref,created_by) VALUES "
                    "(%s,'PROJECT',%s,4,'{}'::jsonb,'PLM','PROJECT_INTERNAL',"
                    "%s,%s,1,0,%s,%s)",
                    (root, facts["project"], b"c" * 32, b"s" * 32,
                     third.reference_version_id, facts["manager"]))

        sql_denied(incomplete_revision)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_versions "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 3
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=facts["port"], database="postgres"))
    try:
        alembic_command.downgrade(cfg, "20261009_0150")
    except RuntimeError as error:
        assert "Reference result lock history prevents downgrade" in str(error)
    else:
        raise AssertionError("revision history was silently downgraded")
    return None


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("SOL_01_A07_REFERENCE_REVISE_OWNER_PG_PASS")
