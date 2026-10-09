"""Win11 isolated PG18 project Session/role proof for GLOBAL candidates."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import GlobalReferenceCandidateCursorCodec
from plm_assistant.modules.solution.application.read_global_reference_candidates import (
    GlobalReferenceCandidateReadError, GlobalReferenceCandidateReadQuery,
    GlobalReferenceCandidateReadService,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_internal_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a02-global-candidate-internal/verify.py")
assert SPEC and SPEC.loader
internal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(internal)
fixture = internal.fixture


def rejects(action, expected: str) -> None:
    try:
        action()
    except GlobalReferenceCandidateReadError as error:
        assert error.code == expected, (error.code, expected)
        return
    raise AssertionError(f"candidate read unexpectedly accepted {expected}")


def on_published(*, runtime, catalog, initial, port, on_http=None) -> None:
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_sessions WHERE session_token_digest=%s",
            (hashlib.sha256(fixture.TOKEN).digest(),)).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('GLBCAND1','glbcand1','Synthetic candidate project',%s) "
            "RETURNING project_id", (actor,)).fetchone()[0]
        other = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('GLBCAND2','glbcand2','Other project',%s) "
            "RETURNING project_id", (actor,)).fetchone()[0]
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
            "RETURNING department_id", (project,)).fetchone()[0]
        member = db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
            "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') "
            "RETURNING project_member_id",
            (project, actor, department)).fetchone()[0]
    reader = GlobalReferenceCandidateReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(),
        license_guard=internal.fixture.SyntheticLicense(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        catalog=catalog,
        cursor=GlobalReferenceCandidateCursorCodec(b"k" * 32))
    query = GlobalReferenceCandidateReadQuery(
        fixture.TOKEN, uuid.uuid4(), project)
    first = reader.list(query, page_size=1)
    assert first.items == () and first.has_more and first.next_cursor
    second = reader.list(query, page_size=1, cursor=first.next_cursor)
    assert len(second.items) == 1 and not second.has_more
    assert second.items[0].reference_solution_id == initial.reference_solution_id
    assert second.items[0].display_label == "审定的合成标签"
    if on_http is not None:
        on_http(reader=reader, project=project, other_project=other,
                initial=initial)
    rejects(lambda: reader.list(
        GlobalReferenceCandidateReadQuery(fixture.TOKEN, uuid.uuid4(), other)),
        "RESOURCE_NOT_FOUND")
    rejects(lambda: reader.list(query, page_size=2, cursor=first.next_cursor),
            "REQUEST_MALFORMED")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER',"
                   "lock_version=lock_version+1 WHERE project_member_id=%s", (member,))
    assert len(reader.list(query).items) == 1
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER',"
                   "lock_version=lock_version+1 WHERE project_member_id=%s", (member,))
    rejects(lambda: reader.list(query), "RESOURCE_NOT_FOUND")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER',"
                   "state='SUSPENDED',lock_version=lock_version+1 "
                   "WHERE project_member_id=%s", (member,))
    rejects(lambda: reader.list(query), "RESOURCE_NOT_FOUND")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE project_member_id=%s", (member,))
        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',"
                   "lock_version=lock_version+1 WHERE project_id=%s", (project,))
    rejects(lambda: reader.list(query), "PROJECT_ARCHIVED")


def on_qualified(**facts) -> None:
    internal.on_qualified(**facts, on_published=on_published)


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A03_P05_A03_GLOBAL_CANDIDATE_OWNER_PG_PASS")
