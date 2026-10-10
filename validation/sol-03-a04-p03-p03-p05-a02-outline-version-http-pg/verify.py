"""Disposable Win11 ASGI/PG verification of opt-in OutlineVersion POST."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.api.outline_version_create import (
    create_outline_version_create_router,
)
from plm_assistant.modules.solution.application.create_outline_version import OutlineVersionCreateService
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef, OutlineRequirementRef, OutlineVersionDraftInput,
)
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.solution.application.set_reference_eligibility import SetReferenceEligibility
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import (
    SqlAlchemyOutlineVersionCreateRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import (
    SqlAlchemyReferenceCreateRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_use_repository import (
    SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_http_dual_scope_helper",
    ROOT / "validation/sol-03-a04-p03-p03-p04-a03-outline-dual-scope-owner/verify.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
fixture, composition = helper.fixture, helper.composition


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def headers(token, csrf, key="outline-http-create-0001"):
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def body(draft: OutlineVersionDraftInput):
    return {
        "section_ids": [str(value) for value in draft.section_ids],
        "requirement_refs": [{
            "requirement_id": str(value.requirement_id),
            "requirement_version_id": str(value.requirement_version_id),
        } for value in draft.requirement_refs],
        "reference_refs": [{
            "scope": value.scope,
            "reference_solution_id": str(value.reference_solution_id),
            "reference_version_id": str(value.reference_version_id),
        } for value in draft.reference_refs],
        "missing_declarations": list(draft.missing_declarations),
        "conflict_declarations": list(draft.conflict_declarations),
    }


def client(*, runtime, audit, license_guard, references):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    owner = OutlineVersionCreateService(
        **helper.common(runtime=runtime, license_guard=license_guard, audit=audit),
        inputs=helper.inputs(references),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    router = create_outline_version_create_router(
        sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        creates=owner)
    return TestClient(
        create_app(solution_outline_version_create_router=router),
        base_url="https://plm.example.test")


def verify_version(*, port, project, outline, version, scope, requirement,
                   requirement_version, reference, reference_version,
                   expected_count=1):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_versions "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == expected_count
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_version_create_results "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == expected_count
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_OUTLINE_VERSION_CREATED' "
            "AND target_object_id=%s", (outline,)).fetchone()[0] == expected_count
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_OUTLINE_VERSION_CREATE'").fetchone()[0] == expected_count
        assert db.execute(
            "SELECT requirement_id,requirement_version_id,ordinal "
            "FROM plm.sol_outline_requirement_refs "
            "WHERE solution_outline_version_id=%s", (version,)).fetchone() == (
                requirement, requirement_version, 1)
        assert db.execute(
            "SELECT reference_solution_id,reference_version_id,reference_scope,"
            "source_project_id,ordinal FROM plm.sol_outline_reference_refs "
            "WHERE solution_outline_version_id=%s", (version,)).fetchone() == (
                reference, reference_version, scope,
                project if scope == "PROJECT" else None, 1)


def project_created(*, runtime, sources, audit, license_guard, created,
                    project, other_project, manager, token, csrf,
                    member_token, member_csrf, downloads, parse_results,
                    scratch, locator, content, port, **_unused):
    references, eligibility, _ = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 0, "ELIGIBLE", "HTTP source reviewed",
        "outline-http-project-eligible-0001"))
    outline, section = helper.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="http-project")
    requirement, requirement_version = helper.seed_approved_requirement(
        port=port, project=project, actor=manager, code="R-OUTLINE-HTTP-P")
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, requirement_version),),
        (OutlineReferenceRef("PROJECT", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
    payload = body(draft)
    with client(runtime=runtime, audit=audit, license_guard=license_guard,
                references=references) as app:
        first = app.post(path, headers=headers(token, csrf), json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["version_no"] == 1 and data["version_state"] == "DRAFT"
        assert first.headers["location"].endswith(data["solution_outline_version_id"])
        assert first.headers["x-trace-id"] == first.json()["trace_id"]
        assert app.post(path, headers=headers(token, csrf), json=payload).json()["data"] == data
        assert app.post(path, headers=headers(token, csrf),
                        json={**payload, "conflict_declarations": [{"note": "changed"}]}).status_code == 409
        verify_version(
            port=port, project=project, outline=outline,
            version=uuid.UUID(data["solution_outline_version_id"]),
            scope="PROJECT", requirement=requirement,
            requirement_version=requirement_version,
            reference=created.reference_solution_id,
            reference_version=created.reference_version_id)
        assert app.post(path, headers=headers(b"u" * 32, b"v" * 32, "customer-denied-0001"),
                        json=payload).status_code == 404
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=headers(token, csrf, "cross-project-0001"),
                        json=payload).status_code == 404
        assert app.post(path, headers=headers(token, b"x" * 32, "bad-csrf-0001"),
                        json=payload).status_code == 403
        member = app.post(path, headers=headers(
            member_token, member_csrf, "member-version-0001"), json=payload)
        assert member.status_code == 201, member.text
        assert member.json()["data"]["version_no"] == 2
        assert member.json()["data"]["supersedes_version_ref"] == data["solution_outline_version_id"]
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        assert app.post(path, headers=headers(token, csrf, "suspended-user-0001"),
                        json=payload).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        source_file = scratch / "private-documents" / locator
        original = source_file.read_bytes()
        try:
            source_file.write_bytes(b"X" * len(content))
            assert app.post(path, headers=headers(token, csrf, "tampered-source-0001"),
                            json=payload).status_code == 503
        finally:
            source_file.write_bytes(original)
    with client(runtime=runtime, audit=audit, license_guard=DeniedLicense(),
                references=references) as denied:
        response = denied.post(path, headers=headers(token, csrf, "license-denied-0001"),
                               json=payload)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers(token, csrf), json=payload).status_code == 404
    verify_version(
        port=port, project=project, outline=outline,
        version=uuid.UUID(data["solution_outline_version_id"]),
        scope="PROJECT", requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id,
        expected_count=2)
    return 0


def global_qualified(*, runtime, request, sources, audit, license_guard,
                     downloads, parse_results, confirmed, port, **_unused):
    references, eligibility, source_common = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    created = ReferenceCreateService(
        **source_common,
        repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(request, composition.global_fixture.CSRF,
                                    "Global HTTP source",
                                    "outline-http-global-reference-0001"))
    eligibility.set(SetReferenceEligibility(
        composition.global_fixture.TOKEN, composition.global_fixture.CSRF,
        uuid.uuid4(), "GLOBAL", None, created.reference_solution_id,
        0, "ELIGIBLE", "Global HTTP source reviewed",
        "outline-http-global-eligible-0001"))
    token, csrf = b"y" * 32, b"z" * 32
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        manager = helper.fixture.user(db, "Outline HTTP Global Manager", token, csrf)
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('SOLHTTPGLOBAL','solhttpglobal',"
            "'HTTP global target',%s) RETURNING project_id",
            (manager,)).fetchone()[0]
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'SOL','sol','Solution') "
            "RETURNING department_id", (project,)).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
            "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
            (project, manager, department))
    outline, section = helper.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="http-global")
    requirement, requirement_version = helper.seed_approved_requirement(
        port=port, project=project, actor=manager, code="R-OUTLINE-HTTP-G")
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, requirement_version),),
        (OutlineReferenceRef("GLOBAL", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
    payload = body(draft)
    with client(runtime=runtime, audit=audit, license_guard=license_guard,
                references=references) as app:
        first = app.post(path, headers=headers(token, csrf, "global-version-0001"),
                         json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["version_no"] == 1
        assert app.post(path, headers=headers(token, csrf, "global-version-0001"),
                        json=payload).json()["data"] == data
    expired = ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=references._sources,
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository(),
        clock=lambda: confirmed.expires_at)
    with client(runtime=runtime, audit=audit, license_guard=license_guard,
                references=expired) as app:
        assert app.post(path, headers=headers(token, csrf, "expired-global-0001"),
                        json=payload).status_code == 503
    verify_version(
        port=port, project=project, outline=outline,
        version=uuid.UUID(data["solution_outline_version_id"]),
        scope="GLOBAL", requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id)


if __name__ == "__main__":
    fixture.main(on_created=project_created)
    composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P03_P03_P05_A02_OUTLINE_VERSION_HTTP_PG_PASS: "
          "real PROJECT/GLOBAL ASGI Session/PG, fixed refs, replay, roles, "
          "CSRF/License, tamper/expiry zero-write, default 404")
