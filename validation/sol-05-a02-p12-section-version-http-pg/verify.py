"""Disposable Win11 ASGI/PG proof for opt-in SectionVersion POST."""

from __future__ import annotations

import importlib.util
import uuid
from functools import partial
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_section_version_create_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_owner_fixture",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def on_http(*, port, scratch, locator, content, runtime, audit, license_guard,
            project, other_project, token, csrf, member_token, member_csrf,
            evidence, document_version, documents, downloads, parse_results,
            section, requirement, requirement_version, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    args = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results,
    )
    try:
        create_windows_section_version_create_router(
            **{**args, "documents": None})
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing Document proof dependency mounted route")
    router = create_windows_section_version_create_router(**args)
    path = f"/api/v1/projects/{project}/solution-sections/{section}/versions"
    payload = {
        "title": "HTTP section body",
        "content_document_version_ref": str(document_version),
        "content_artifact_ref": None,
        "requirement_refs": [{
            "requirement_id": str(requirement),
            "requirement_version_id": str(requirement_version),
        }],
        "evidence_ids": [str(evidence)],
        "assumptions": [{"note": "synthetic http"}], "exclusions": [],
    }
    with TestClient(create_app(
            solution_section_version_create_router=router),
            base_url="https://plm.example.test") as app:
        first = app.post(path, headers=headers(token, csrf, "section-http-create-0001"),
                         json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["version_no"] == 6 and data["version_state"] == "DRAFT"
        assert data["requirement_refs"] == payload["requirement_refs"]
        assert data["evidence_ids"] == payload["evidence_ids"]
        assert first.headers["location"] == path + "/" + data["solution_section_version_id"]
        replay = app.post(path, headers=headers(token, csrf, "section-http-create-0001"),
                          json=payload)
        assert replay.status_code == 201 and replay.json()["data"] == data
        assert app.post(path, headers=headers(token, csrf, "section-http-create-0001"),
                        json={**payload, "title": "Different"}).status_code == 409
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=headers(token, csrf, "section-cross-project-0001"),
                        json=payload).status_code == 404
        assert app.post(path, headers=headers(token, b"x" * 32,
                                             "section-bad-csrf-0001"),
                        json=payload).status_code == 403
        bad_origin = headers(token, csrf, "section-bad-origin-0001")
        bad_origin["origin"] = "https://evil.test"
        assert app.post(path, headers=bad_origin, json=payload).status_code == 403
        missing_key = headers(token, csrf, "section-no-key-0001")
        del missing_key["idempotency-key"]
        assert app.post(path, headers=missing_key, json=payload).status_code == 422
        artifact = {**payload, "content_document_version_ref": None,
                    "content_artifact_ref": str(uuid.uuid4())}
        assert app.post(path, headers=headers(token, csrf,
                                              "section-artifact-closed-0001"),
                        json=artifact).status_code == 503
        member = app.post(path, headers=headers(
            member_token, member_csrf, "section-member-http-0001"), json=payload)
        assert member.status_code == 201 and member.json()["data"]["version_no"] == 7
        source_path = scratch / "private-documents" / locator
        source_path.write_bytes(b"X" * len(content))
        assert app.post(path, headers=headers(token, csrf,
                                              "section-file-tamper-0001"),
                        json=payload).status_code == 503
        assert app.post(path, headers=headers(token, csrf,
                                              "section-http-create-0001"),
                        json=payload).json()["data"] == data
        source_path.write_bytes(content)
    denied_router = create_windows_section_version_create_router(
        **{**args, "license_guard": DeniedLicense()})
    with TestClient(create_app(
            solution_section_version_create_router=denied_router),
            base_url="https://plm.example.test") as denied:
        assert denied.post(path, headers=headers(token, csrf,
                                                "section-license-denied-0001"),
                           json=payload).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 7
        assert db.execute("SELECT count(*) FROM plm.sol_section_version_create_results "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 7
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_SECTION_VERSION_CREATED'").fetchone()[0] == 7
    print("SOL_05_A02_P12_SECTION_VERSION_HTTP_PG_PASS: optional Windows "
          "router, real Session/PG/source, replay, role/isolation, tamper and fail closed")


if __name__ == "__main__":
    prior.prior.main(on_created=partial(prior.on_created, on_http=on_http))
