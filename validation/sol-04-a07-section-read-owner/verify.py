"""Win11 disposable PG proof of authorized current SolutionSection GET owner."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_section import CreateSection, SectionCreateService
from plm_assistant.modules.solution.application.read_section import (
    SectionReadError, SectionReadQuery, SectionReadService,
)
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def rejects(code: str, action) -> None:
    try:
        action()
    except SectionReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, member, token, csrf, member_token, member_csrf,
               **_unused) -> int:
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    common = dict(unit_of_work=runtime.unit_of_work,
                  license_guard=license_guard, authorization=authorization)
    writes = dict(**common, access=SqlAlchemyProjectWriteAccess(),
                  receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    outline = OutlineCreateService(
        **writes, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          "Read section parent", "section-read-parent-0001"))
    section = SectionCreateService(
        **writes, repository=SqlAlchemySectionCreateRepository()).create(
            CreateSection(token, csrf, uuid.uuid4(), project,
                          outline.solution_outline_id, "Scope", "section-read-0001"))
    reads = dict(**common, access=SqlAlchemyProjectReadAccess(),
                 repository=SqlAlchemySectionReadRepository())
    service = SectionReadService(**reads)
    query = SectionReadQuery(token, uuid.uuid4(), project)
    view = service.get_current(query, section.solution_section_id)
    assert view.solution_section_id == section.solution_section_id
    assert view.solution_outline_id == outline.solution_outline_id
    assert view.project_id == project and view.section_key == "Scope"
    assert view.section_state == "ACTIVE" and view.current_approved_version_ref is None
    assert view.created_by == manager and view.etag == '"v0"'
    assert service.get_current(SectionReadQuery(member_token, uuid.uuid4(), project),
                               section.solution_section_id) == view
    assert service.get_current(SectionReadQuery(b"u" * 32, uuid.uuid4(), project),
                               section.solution_section_id) == view
    rejects("VALIDATION_FAILED", lambda: service.get_current(
        replace(query, session_token=b"short"), section.solution_section_id))
    rejects("RESOURCE_NOT_FOUND", lambda: service.get_current(query, uuid.uuid4()))
    rejects("RESOURCE_NOT_FOUND", lambda: service.get_current(
        replace(query, project_id=other_project), section.solution_section_id))
    rejects("AUTH_ACCESS_DENIED", lambda: service.get_current(
        replace(query, session_token=b"z" * 32), section.solution_section_id))
    rejects("LICENSE_OPERATION_DENIED", lambda: SectionReadService(
        **{**reads, "license_guard": DeniedLicense()}).get_current(
            query, section.solution_section_id))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejects("RESOURCE_NOT_FOUND", lambda: service.get_current(
        SectionReadQuery(member_token, uuid.uuid4(), project), section.solution_section_id))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',"
                   "lock_version=lock_version+1 WHERE project_id=%s", (project,))
    assert service.get_current(query, section.solution_section_id) == view
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER ALL")
        try:
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=%s "
                       "WHERE solution_section_id=%s",
                       (uuid.uuid4(), section.solution_section_id))
            rejects("SOLUTION_UNAVAILABLE", lambda: service.get_current(
                query, section.solution_section_id))
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=NULL,"
                       "section_state='ARCHIVED',lock_version=lock_version+1 "
                       "WHERE solution_section_id=%s", (section.solution_section_id,))
            archived = service.get_current(query, section.solution_section_id)
            assert archived.section_state == "ARCHIVED" and archived.etag == '"v1"'
            db.execute("UPDATE plm.sol_sections SET section_state='ACTIVE',"
                       "lock_version=0 WHERE solution_section_id=%s",
                       (section.solution_section_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER ALL")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_sections WHERE solution_section_id=%s",
            (section.solution_section_id,)).fetchone()[0] == 1
        db.execute("UPDATE plm.prj_projects SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE project_id=%s", (project,))
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    return 0


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    print("SOL_04_A07_SECTION_READ_OWNER_PASS: real Session/PG, current members, "
          "cross-project/paused/License denial, archived project read")
