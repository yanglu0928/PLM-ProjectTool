"""Win11 disposable PG/HTTP proof: revoking GLOBAL confirmation hides candidate."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_version_create_router,
)
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_project_global_reference_candidate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec,
)
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeService,
    RevokeReferenceDeidentification,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_revocation_repository import (
    SqlAlchemyReferenceDeidentificationRevocationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_browser_fixture_for_revoke",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a06-p03-global-candidate-browser/serve.py")
assert SPEC and SPEC.loader
browser_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(browser_fixture)
factory_fixture = browser_fixture.factory_fixture
owner_fixture = factory_fixture.http_fixture.owner_fixture
fixture = factory_fixture.http_fixture.fixture


class ExpectedFixtureStop(Exception):
    """Successful test stops before the upstream fixture revokes Evidence."""


def on_http(*, runtime, project, initial, port, audit, license_guard,
            document_storage_root, parse_result_storage_root, **facts) -> None:
    factory_fixture.on_http(
        runtime=runtime, project=project, initial=initial, port=port,
        audit=audit, license_guard=license_guard,
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root, **facts)
    token, csrf = fixture.TOKEN, fixture.CSRF
    outline, section = browser_fixture.outline_helper.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project,
        suffix="candidate-confirmation-revoke")
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
        confirmation_rows = db.execute(
            "SELECT confirmation_id FROM plm.sol_reference_deidentification_confirmations "
            "WHERE revoked_at IS NULL").fetchall()
        assert len(confirmation_rows) == 1
        confirmation = confirmation_rows[0][0]
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_versions WHERE solution_outline_id=%s",
            (outline,)).fetchone()[0] == 0
    with TestClient(app, base_url="https://plm.example.test") as client:
        before = client.get(path, headers=headers)
        assert before.status_code == 200, before.text
        assert [item["reference_solution_id"] for item in before.json()["data"]["items"]] == [
            str(initial.reference_solution_id)]
        revoked = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit).revoke(
                RevokeReferenceDeidentification(
                    confirmation, token, csrf, uuid.uuid4(),
                    "ADMIN_REVIEW", "candidate-confirmation-revoke-0001"))
        assert revoked.confirmation_id == confirmation
        after = client.get(path, headers=headers)
        assert after.status_code == 200, after.text
        assert after.json()["data"]["items"] == []
        refused = client.post(
            write, headers={**headers, "x-csrf-token": csrf.hex(),
                            "idempotency-key": "candidate-confirmation-create-0001"},
            json=body)
        assert refused.status_code == 503, refused.text
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
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
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_REFERENCE_DEIDENTIFICATION_REVOKED' "
            "AND target_object_id=%s", (confirmation,)).fetchone()[0] == 1
    print("GLOBAL_CANDIDATE_CONFIRMATION_REVOKE_PASS: GET hidden, CREATE refused, single revocation Audit")
    raise ExpectedFixtureStop()


def on_qualified(**facts) -> None:
    owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        owner_fixture.on_published(**published, on_http=on_http))


if __name__ == "__main__":
    try:
        fixture.main(on_qualified=on_qualified)
    except ExpectedFixtureStop:
        print("SOL_03_A04_P03_P03_P06_A04_P01_P02_P01_CONFIRMATION_REVOKE_PG_PASS")
