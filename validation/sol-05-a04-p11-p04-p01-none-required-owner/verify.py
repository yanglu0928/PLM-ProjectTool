"""Disposable Win11/PG18 HTTP proof for explicit NONE_REQUIRED SectionVersion."""

from __future__ import annotations

import importlib.util
from functools import partial
from pathlib import Path
import uuid

from alembic import command
import psycopg
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_version_create_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_http_fixture",
    ROOT / "validation/sol-05-a02-p12-section-version-http-pg/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_http(*, port, runtime, audit, license_guard, project, section,
            other_project, token, csrf, evidence, document_version,
            requirement, requirement_version, documents, downloads,
            parse_results, **kwargs):
    prior.on_http(
        port=port, runtime=runtime, audit=audit, license_guard=license_guard,
        project=project, section=section, other_project=other_project,
        token=token, csrf=csrf, evidence=evidence,
        document_version=document_version, requirement=requirement,
        requirement_version=requirement_version, documents=documents,
        downloads=downloads, parse_results=parse_results, **kwargs)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_version_create_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit, documents=documents,
        downloads=downloads, parse_results=parse_results)
    path = f"/api/v1/projects/{project}/solution-sections/{section}/versions"
    payload = {
        "title": "HTTP section body",
        "content_document_version_ref": str(document_version),
        "content_artifact_ref": None,
        "requirement_refs": [{"requirement_id": str(requirement),
                              "requirement_version_id": str(requirement_version)}],
        "evidence_ids": [str(evidence)],
        "assumptions": [{"note": "synthetic http"}], "exclusions": [],
        "spec_binding_state": "NONE_REQUIRED",
        "spec_not_required_reason": "No specialist design for this section",
    }
    fixed = {**payload, "spec_binding_state": "FIXED_REFS",
             "spec_not_required_reason": None,
             "structured_spec_refs": [{"spec_series_id": str(uuid.uuid4()),
                                       "structured_solution_spec_id": str(uuid.uuid4())}]}
    with TestClient(create_app(solution_section_version_create_router=router),
                    base_url="https://plm.example.test") as app:
        headers = prior.headers(token, csrf, "section-none-required-0001")
        first = app.post(path, headers=headers, json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["version_no"] == 8 and data["version_state"] == "DRAFT"
        assert "spec_binding_state" not in data  # frozen first-201 shape
        replay = app.post(path, headers=headers, json=payload)
        assert replay.status_code == 201 and replay.json()["data"] == data
        assert app.post(path, headers=headers, json={
            **payload, "spec_not_required_reason": "Changed reason"}).status_code == 409
        assert app.post(path, headers=prior.headers(
            token, csrf, "section-fixed-closed-0001"), json=fixed).status_code == 503
        assert app.post(path, headers=prior.headers(
            token, csrf, "section-invalid-none-0001"),
            json={**payload, "spec_not_required_reason": " "}).status_code == 422
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=prior.headers(token, csrf, "section-none-cross-0001"),
                        json=payload).status_code == 404
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT spec_binding_state,spec_not_required_reason,declared_spec_count "
            "FROM plm.sol_section_versions WHERE solution_section_version_id=%s",
            (uuid.UUID(data["solution_section_version_id"]),)).fetchone()
        assert version == ("NONE_REQUIRED", payload["spec_not_required_reason"], 0)
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 8
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                          "WHERE operation='V1_SOL_SECTION_VERSION_CREATE'").fetchone()[0] == 8
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_SECTION_VERSION_CREATED'").fetchone()[0] == 8
    with runtime.unit_of_work() as tx:
        view = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section,
            version_id=uuid.UUID(data["solution_section_version_id"]))
        assert view is not None
        assert view.spec_binding_state == "NONE_REQUIRED"
        assert view.spec_not_required_reason == payload["spec_not_required_reason"]
        assert view.structured_spec_refs == ()
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    try:
        command.downgrade(cfg, "20261023_0178")
    except RuntimeError as error:
        assert "SectionVersion Spec binding history prevents downgrade" in str(error)
    else:
        raise AssertionError("declared SectionVersion history must block downgrade")
    print("SOL_05_A04_P11_P04_P01_NONE_REQUIRED_OWNER_PASS: real HTTP/PG "
          "declaration, old 201 replay, same-key conflict, fixed refs closed, "
          "project isolation, receipt/audit and history-safe downgrade")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=partial(
        prior.prior.on_created, on_http=on_http))
