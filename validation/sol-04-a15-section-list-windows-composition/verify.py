"""Win11 explicit Section LIST composition over real ASGI/PG fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_section_create_router,
    create_windows_section_list_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_list_http_fixture",
    ROOT / "validation/sol-04-a14-section-list-http-pg/verify.py")
assert SPEC and SPEC.loader
http_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http_fixture)


def on_created(*, port, runtime, audit, license_guard, project, token, csrf,
               **kwargs) -> int:
    try:
        create_windows_section_list_router(
            runtime=None, sessions=None, origins=None,
            license_guard=None, cursors=None)
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing trust dependencies accepted")
    try:
        create_windows_section_list_router(
            runtime=runtime, sessions=object(), origins=object(),
            license_guard=license_guard, cursors=object())
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("wrong cursor family accepted")
    http_fixture.on_created(
        port=port, runtime=runtime, audit=audit,
        license_guard=license_guard, project=project,
        token=token, csrf=csrf, **kwargs,
        create_router_factory=create_windows_section_list_router)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        outline_id = db.execute(
            "SELECT solution_outline_id FROM plm.sol_outlines WHERE "
            "project_id=%s AND name='Read section parent'", (project,)).fetchone()[0]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    list_router = create_windows_section_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=SectionListCursorCodec(b"q" * 32))
    create_router = create_windows_section_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit)
    path = f"/api/v1/projects/{project}/solution-sections"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test",
               "x-csrf-token": csrf.hex(),
               "idempotency-key": "section-list-windows-write-0001"}
    with TestClient(create_app(
            solution_section_create_router=create_router,
            solution_section_list_router=list_router),
            base_url="https://plm.example.test") as client:
        created = client.post(path, headers=headers,
                              json={"solution_outline_id": str(outline_id),
                                    "section_key": "Write mode"})
        assert created.status_code == 201, created.text
        listed = client.get(path, headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["data"]["items"]) == 4
    return 0


if __name__ == "__main__":
    http_fixture.prior.prior.fixture.main(on_created=on_created)
    print("SOL_04_A15_SECTION_LIST_WINDOWS_COMPOSITION_PASS: explicit Windows "
          "read/write, real Session/ASGI/PG, denied trust and write coexistence")
