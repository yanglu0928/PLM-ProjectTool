"""Win11 disposable PG/HTTP proof: GLOBAL revision invalidates old publication."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import create_windows_outline_version_create_router
from plm_assistant.entrypoints.windows_solution_reference import create_windows_project_global_reference_candidate_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import GlobalReferenceCandidateCursorCodec
from plm_assistant.modules.solution.application.revise_reference_solution import ReferenceReviseService, ReviseReferenceSolution
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_revoke_fixture_for_revision",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a04-p01-p02-p01-confirmation-revoke/verify.py")
assert SPEC and SPEC.loader
revoke_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(revoke_fixture)
browser_fixture = revoke_fixture.browser_fixture
factory_fixture = revoke_fixture.factory_fixture
owner_fixture = revoke_fixture.owner_fixture
fixture = revoke_fixture.fixture


class ExpectedFixtureStop(Exception):
    """Successful revision proof stops before upstream old-version operations."""


def on_http(*, runtime, project, initial, port, audit, license_guard,
            document_storage_root, parse_result_storage_root,
            request, sources, **facts) -> None:
    factory_fixture.on_http(
        runtime=runtime, project=project, initial=initial, port=port,
        audit=audit, license_guard=license_guard,
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root, **facts)
    token, csrf = fixture.TOKEN, fixture.CSRF
    outline, section = browser_fixture.outline_helper.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project,
        suffix="candidate-version-revise")
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    common = dict(runtime=runtime, sessions=sessions, origins=origins,
                  license_guard=license_guard)
    app = create_app(
        project_global_reference_candidate_router=(
            create_windows_project_global_reference_candidate_router(
                **common, cursors=GlobalReferenceCandidateCursorCodec(b"g" * 32),
                document_storage_root=document_storage_root,
                parse_result_storage_root=parse_result_storage_root)),
        solution_outline_version_create_router=create_windows_outline_version_create_router(
            **common, audit=audit,
            document_storage_root=document_storage_root,
            parse_result_storage_root=parse_result_storage_root),
    )
    path = f"/api/v1/projects/{project}/global-reference-candidates"
    write = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    body = {
        "section_ids": [str(section)], "requirement_refs": [],
        "reference_refs": [{
            "scope": "GLOBAL",
            "reference_solution_id": str(initial.reference_solution_id),
            "reference_version_id": str(initial.reference_version_id),
        }], "missing_declarations": [], "conflict_declarations": [],
    }
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        lock_version = db.execute(
            "SELECT lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s",
            (initial.reference_solution_id,)).fetchone()[0]
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_versions WHERE solution_outline_id=%s",
            (outline,)).fetchone()[0] == 0
    with TestClient(app, base_url="https://plm.example.test") as client:
        before = client.get(path, headers=headers)
        assert before.status_code == 200, before.text
        assert [item["reference_version_id"] for item in before.json()["data"]["items"]] == [
            str(initial.reference_version_id)]
        revised = ReferenceReviseService(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            license_guard=license_guard, sources=sources,
            repository=SqlAlchemyReferenceReviseRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit).revise(
                ReviseReferenceSolution(
                    request, csrf, initial.reference_solution_id, lock_version,
                    "candidate-revise-old-publish-0001"))
        assert revised.reference_solution_id == initial.reference_solution_id
        assert revised.reference_version_id != initial.reference_version_id
        assert revised.version_no == 2
        after = client.get(path, headers=headers)
        assert after.status_code == 200, after.text
        assert after.json()["data"]["items"] == []
        refused = client.post(
            write, headers={**headers, "x-csrf-token": csrf.hex(),
                            "idempotency-key": "candidate-revise-create-0001"},
            json=body)
        assert refused.status_code == 503, refused.text
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT current_version_ref FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s",
            (initial.reference_solution_id,)).fetchone()[0] == revised.reference_version_id
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_versions WHERE solution_outline_id=%s",
            (outline,)).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_OUTLINE_VERSION_CREATED' "
            "AND target_object_id=%s", (outline,)).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_OUTLINE_VERSION_CREATE'").fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_REVISED' "
            "AND target_object_id=%s", (initial.reference_solution_id,)).fetchone()[0] == 1
    print("GLOBAL_CANDIDATE_VERSION_REVISE_PASS: old publication hidden, CREATE refused, single revision Audit")
    raise ExpectedFixtureStop()


def on_qualified(**facts) -> None:
    owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        owner_fixture.on_published(
            **published, on_http=lambda **http_facts:
            on_http(**http_facts, request=facts["request"], sources=facts["sources"])))


if __name__ == "__main__":
    try:
        fixture.main(on_qualified=on_qualified)
    except ExpectedFixtureStop:
        print("SOL_03_A04_P03_P03_P06_A04_P01_P03_VERSION_REVISE_PG_PASS")
