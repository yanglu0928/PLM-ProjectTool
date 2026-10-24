"""Win11 disposable PG/HTTP proof of expired GLOBAL confirmation via service clock."""

from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.application.prove_reference_use_document import ReferenceUseDocumentProofService
from plm_assistant.modules.document.application.prove_reference_use_parse import ReferenceUseParseProofService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.reference_use_source import SqlAlchemyReferenceUseDocumentSource
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import ReferenceUseEvidenceProofService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.global_reference_candidates import create_project_global_reference_candidate_router
from plm_assistant.modules.solution.api.outline_version_create import create_outline_version_create_router
from plm_assistant.modules.solution.application.create_outline_version import OutlineVersionCreateService
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import GlobalReferenceCandidateCursorCodec
from plm_assistant.modules.solution.application.list_global_reference_candidates import GlobalReferenceCandidateCatalog
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.solution.application.read_global_reference_candidates import GlobalReferenceCandidateReadService
from plm_assistant.modules.solution.infrastructure.global_reference_candidate_repository import SqlAlchemyGlobalReferenceCandidateRepository
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import SqlAlchemyOutlineVersionCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import (
    SqlAlchemyCurrentGlobalConfirmationRepository,
    SqlAlchemyCurrentReferenceUseRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_use_source import CurrentReferenceSourceAdapter


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_browser_fixture_for_expiry",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a06-p03-global-candidate-browser/serve.py")
assert SPEC and SPEC.loader
browser_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(browser_fixture)
factory_fixture = browser_fixture.factory_fixture
owner_fixture = factory_fixture.http_fixture.owner_fixture
fixture = factory_fixture.http_fixture.fixture


def expired_proof(*, document_storage_root, parse_result_storage_root, instant):
    documents = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=LocalFileStorage(document_storage_root))
    parses = ReferenceUseParseProofService(
        documents=documents, metadata=SqlAlchemyParseResultReadRepository(),
        storage=LocalParseResultStorage(parse_result_storage_root))
    evidence = ReferenceUseEvidenceProofService(
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=documents, parses=parses)
    return ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=CurrentReferenceSourceAdapter(documents=documents, evidence=evidence),
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository(),
        clock=lambda: instant)


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
        suffix="candidate-confirmation-expiry")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rows = db.execute(
            "SELECT expires_at FROM plm.sol_reference_deidentification_confirmations "
            "WHERE revoked_at IS NULL").fetchall()
        assert len(rows) == 1
        instant = rows[0][0]
    proof = expired_proof(
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root,
        instant=instant)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    catalog = GlobalReferenceCandidateCatalog(
        repository=SqlAlchemyGlobalReferenceCandidateRepository(), proof=proof)
    reader = GlobalReferenceCandidateReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=authorization, catalog=catalog,
        cursor=GlobalReferenceCandidateCursorCodec(b"g" * 32))
    before_proof = expired_proof(
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root,
        instant=instant - timedelta(microseconds=1))
    before_reader = GlobalReferenceCandidateReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=authorization,
        catalog=GlobalReferenceCandidateCatalog(
            repository=SqlAlchemyGlobalReferenceCandidateRepository(), proof=before_proof),
        cursor=GlobalReferenceCandidateCursorCodec(b"g" * 32))
    creator = OutlineVersionCreateService(
        **browser_fixture.outline_helper.common(
            runtime=runtime, license_guard=license_guard, audit=audit),
        inputs=browser_fixture.outline_helper.inputs(proof),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    app = create_app(
        project_global_reference_candidate_router=create_project_global_reference_candidate_router(
            sessions=sessions, origins=origins, reads=reader),
        solution_outline_version_create_router=create_outline_version_create_router(
            sessions=sessions, origins=origins, creates=creator),
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
    with TestClient(create_app(
            project_global_reference_candidate_router=create_project_global_reference_candidate_router(
                sessions=sessions, origins=origins, reads=before_reader)),
            base_url="https://plm.example.test") as before_client:
        before = before_client.get(path, headers=headers)
        assert before.status_code == 200, before.text
        assert [item["reference_solution_id"] for item in before.json()["data"]["items"]] == [
            str(initial.reference_solution_id)]
    with TestClient(app, base_url="https://plm.example.test") as client:
        hidden = client.get(path, headers=headers)
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["data"]["items"] == []
        refused = client.post(
            write, headers={**headers, "x-csrf-token": csrf.hex(),
                            "idempotency-key": "candidate-expired-create-0001"},
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
    print("GLOBAL_CANDIDATE_CONFIRMATION_EXPIRY_PASS: before deadline visible, exact deadline hides GET and refuses CREATE")


def on_qualified(**facts) -> None:
    owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        owner_fixture.on_published(**published, on_http=on_http))


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A04_P01_P02_P02_CONFIRMATION_EXPIRY_PG_PASS")
