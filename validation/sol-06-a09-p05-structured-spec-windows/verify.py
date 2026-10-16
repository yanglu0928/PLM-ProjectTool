"""Disposable Win11 ASGI/PG18 SOL-06 Windows CREATE composition proof."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_structured_spec_create_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol05_owner_for_sol06_windows",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def on_http(*, port, runtime, audit, license_guard, project, other_project,
            token, csrf, member_token, member_csrf, section, requirement,
            requirement_version, evidence, documents, downloads, parse_results,
            read_router_factory=None, list_router_factory=None,
            list_cursors=None, on_read=None, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    args = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads, parse_results=parse_results)
    try:
        create_windows_structured_spec_create_router(
            **{**args, "documents": None})
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing document source mounted SOL-06 CREATE")
    router = create_windows_structured_spec_create_router(**args)
    read_router = (read_router_factory(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard)
        if read_router_factory is not None else None)
    list_router = (list_router_factory(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=list_cursors)
        if list_router_factory is not None else None)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC LIMIT 1",
            (section,)).fetchone()[0]
    path = f"/api/v1/projects/{project}/structured-solution-specs"
    body = {
        "spec_type": "MIGRATION_SPEC", "payload": {
            "assumptions": ["synthetic pending confirmation"],
            "exclusions": [], "source_system": "old", "target_system": "new",
            "scope": "parts", "cleansing_rules": ["deduplicate"],
            "field_mappings": [{"source": "old_id", "target": "part_id"}],
            "trial_plan": "trial", "reconciliation_plan": "reconcile",
            "rollback_plan": "snapshot", "acceptance_criteria": "zero difference",
        },
        "requirement_refs": [{"requirement_id": str(requirement),
                              "requirement_version_id": str(requirement_version)}],
        "section_refs": [{"solution_section_id": str(section),
                          "solution_section_version_id": str(version)}],
        "evidence_ids": [str(evidence)], "artifact_ids": [],
    }
    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.post(path, headers=headers(token, csrf, "closed-key-000001"),
                           json=body).status_code == 404
    with TestClient(create_app(solution_structured_spec_create_router=router,
                               solution_structured_spec_list_router=list_router,
                               solution_structured_spec_read_router=read_router),
                    base_url="https://plm.example.test") as app:
        first = app.post(path, headers=headers(token, csrf, "first-key-0000001"),
                         json=body)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["version_no"] == 1 and data["version_state"] == "DRAFT"
        assert data["section_refs"] == body["section_refs"]
        assert first.headers["location"].endswith(data["structured_solution_spec_id"])
        replay = app.post(path, headers=headers(token, csrf, "first-key-0000001"),
                          json=body)
        assert replay.status_code == 201 and replay.json()["data"] == data
        assert replay.json()["trace_id"] != first.json()["trace_id"]
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=headers(token, csrf, "other-key-0000001"),
                        json=body).status_code == 404
        assert app.post(path, headers=headers(token, b"x" * 32,
                                              "csrf-key-00000001"),
                        json=body).status_code == 403
        assert app.post(path, headers=headers(token, csrf, "artifact-key-0001"),
                        json={**body, "artifact_ids": [str(uuid.uuid4())]}
                        ).status_code == 422
        member = app.post(path, headers=headers(
            member_token, member_csrf, "member-key-000001"), json=body)
        assert member.status_code == 201 and member.json()["data"]["version_no"] == 1
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute("SELECT count(*) FROM plm.sol_structured_specs").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                              "WHERE operation='V1_SOL_STRUCTURED_SPEC_CREATE'").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.aud_events "
                              "WHERE action='SOL_STRUCTURED_SPEC_CREATED'").fetchone()[0] == 2
        if on_read is not None:
            on_read(app=app, project=project, other_project=other_project,
                    token=token, member_token=member_token,
                    first=data, member=member.json()["data"])
    print("SOL_06_A09_P05_WINDOWS_HTTP_PG_PASS: closed default, real Auth/Source/"
          "PG CREATE/replay/member, one receipt and audit per draft")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_http))
