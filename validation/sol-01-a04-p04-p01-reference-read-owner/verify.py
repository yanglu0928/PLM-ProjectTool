"""Disposable PG18 proof of authorized PROJECT Reference fixed-source read."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceReadError, ReferenceReadQuery, ReferenceReadService,
)
from plm_assistant.modules.solution.infrastructure.reference_read_repository import SqlAlchemyReferenceReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
project_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_fixture)


def rejected(code: str, action) -> None:
    try:
        action()
    except ReferenceReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("unqualified Reference read accepted")


def on_created(*, port, runtime, license_guard, project, other_project,
               manager, member, created, member_created, global_version,
               document_version, evidence, token, member_token, **_unused) -> None:
    reader = ReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyReferenceReadRepository(),
    )
    query = ReferenceReadQuery(token, uuid.uuid4(), project)
    current = reader.get_current(query, created.reference_solution_id)
    assert current.reference_version_id == created.reference_version_id
    assert current.document_version_ids == (document_version,)
    assert len(current.document_refs) == 1
    assert current.document_refs[0].document_version_id == document_version
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        (expected_document_id,) = db.execute(
            "SELECT document_id FROM plm.doc_document_versions "
            "WHERE document_version_id=%s", (document_version,)).fetchone()
    assert current.document_refs[0].document_id == expected_document_id
    assert current.evidence_ids == (evidence,)
    assert current.eligibility_state == "REFERENCE_ONLY"
    assert current.version_state == "DRAFT" and current.version_no == 1
    assert current.etag == '"v0"' and current.scope == "PROJECT"
    assert current.source_fingerprint == created.source_fingerprint
    assert reader.get_current(
        ReferenceReadQuery(member_token, uuid.uuid4(), project),
        created.reference_solution_id) == current
    assert reader.get_current(
        ReferenceReadQuery(b"u" * 32, uuid.uuid4(), project),
        created.reference_solution_id) == current
    assert reader.get_current(query, member_created.reference_solution_id).evidence_ids == ()
    rejected("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        ReferenceReadQuery(token, uuid.uuid4(), other_project),
        created.reference_solution_id))
    rejected("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        query, uuid.uuid4()))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejected("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        ReferenceReadQuery(member_token, uuid.uuid4(), project),
        created.reference_solution_id))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
        db.execute("INSERT INTO plm.sol_reference_document_refs("
                   "reference_version_id,reference_solution_id,scope,"
                   "document_version_id,ordinal) VALUES (%s,%s,'PROJECT',%s,2)",
                   (created.reference_version_id, created.reference_solution_id,
                    global_version))
    rejected("SOLUTION_UNAVAILABLE", lambda: reader.get_current(
        query, created.reference_solution_id))


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P04_P01_REFERENCE_READ_OWNER_PG_PASS: current fixed refs, "
          "PM/IM/customer member, cross-project and revoked member, "
          "rogue GLOBAL source projection denied")


if __name__ == "__main__":
    main()
