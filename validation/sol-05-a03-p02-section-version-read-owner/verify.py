"""Disposable Win11 PG proof for authorized fixed SectionVersion history."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionReadError, SectionVersionReadQuery, SectionVersionReadService,
)
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_owner_for_read",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def service(runtime, license_guard):
    return SectionVersionReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
    )


def rejects(code, action):
    try:
        action()
    except SectionVersionReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected SectionVersion read rejection: " + code)


def on_read(*, port, scratch, locator, content, runtime, license_guard,
            project, other_project, token, member_token, section,
            document_version, requirement, requirement_version, evidence,
            **_unused):
    reader = service(runtime, license_guard)
    query = SectionVersionReadQuery(token, uuid.uuid4(), project, section)
    before = None
    versions = []
    for expected in (5, 3, 1):
        page = reader.list(query, page_size=2, before_version_no=before)
        assert page.items[0].version_no == expected
        versions.extend(page.items)
        before = page.next_before_version_no
        if expected == 1:
            assert not page.has_more and before is None
        else:
            assert page.has_more and before == expected - 1
    assert [item.version_no for item in versions] == [5, 4, 3, 2, 1]
    for item in versions:
        assert item.content_document_version_ref == document_version
        assert item.content_artifact_ref is None
        assert item.requirement_refs[0].requirement_id == requirement
        assert item.requirement_refs[0].requirement_version_id == requirement_version
        assert item.evidence_ids == (evidence,)
        assert reader.get(query, item.solution_section_version_id) == item
    member_query = SectionVersionReadQuery(member_token, uuid.uuid4(), project, section)
    assert reader.get(member_query, versions[0].solution_section_version_id) == versions[0]
    rejects("RESOURCE_NOT_FOUND", lambda: reader.list(
        SectionVersionReadQuery(token, uuid.uuid4(), other_project, section)))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get(
        SectionVersionReadQuery(token, uuid.uuid4(), project, uuid.uuid4()),
        versions[0].solution_section_version_id))
    rejects("AUTH_ACCESS_DENIED", lambda: reader.get(
        SectionVersionReadQuery(b"x" * 32, uuid.uuid4(), project, section),
        versions[0].solution_section_version_id))
    rejects("LICENSE_OPERATION_DENIED", lambda: service(
        runtime, DeniedLicense()).list(query))
    source_path = scratch / "private-documents" / locator
    source_path.write_bytes(b"X" * len(content))
    try:
        assert reader.get(query, versions[0].solution_section_version_id) == versions[0]
    finally:
        source_path.write_bytes(content)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version_id = versions[0].solution_section_version_id
        original = db.execute(
            "SELECT title FROM plm.sol_section_version_create_results WHERE "
            "solution_section_version_id=%s", (version_id,)).fetchone()[0]
        try:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.sol_section_version_create_results "
                           "SET title='Synthetic corrupt first result' WHERE "
                           "solution_section_version_id=%s", (version_id,))
            rejects("SOLUTION_UNAVAILABLE", lambda: reader.get(query, version_id))
        finally:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.sol_section_version_create_results SET "
                           "title=%s WHERE solution_section_version_id=%s",
                           (original, version_id))
        assert reader.get(query, version_id) == versions[0]
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions WHERE "
                          "solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='SOL_SECTION_VERSION_CREATED'").fetchone()[0] == 5
    print("SOL_05_A03_P02_SECTION_VERSION_READ_OWNER_PG_PASS: fixed five-version "
          "history, member, isolation/Auth/License, source drift and no writes")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_read))
