"""Disposable Win11/PG18 Section VALIDATE current Spec qualification."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_spec_current_fit_fixture",
    ROOT / "validation/sol-05-a04-p12-p04-p02-spec-fit-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
fixture = prior.fixture
_fit_owner = prior._after_submit


def _after_submit(*, port, runtime, project, draft, token, csrf, audit,
                  license_guard, documents, downloads, parse_results, **context):
    _fit_owner(
        port=port, runtime=runtime, project=project, draft=draft,
        token=token, csrf=csrf, audit=audit, license_guard=license_guard,
        documents=documents, downloads=downloads,
        parse_results=parse_results, **context)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres")
    with psycopg.connect(**connection) as database:
        rows = database.execute(
            "SELECT v.solution_section_id,v.solution_section_version_id,"
            "v.version_no,r.fit_rationale,r.structured_solution_spec_id "
            "FROM plm.sol_section_versions v JOIN plm.sol_section_spec_refs r "
            "ON r.solution_section_version_id=v.solution_section_version_id "
            "WHERE v.project_id=%s ORDER BY v.version_no", (project,)).fetchall()
        assert len(rows) == 2 and rows[0][2] < rows[1][2]
        assert rows[0][3] is None and rows[1][3]
    section_id, old_id, _, _, spec_id = rows[0]
    new_id = rows[1][1]
    assert rows[1][0] == section_id and rows[1][4] == spec_id
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_version_validate_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    base = (f"/api/v1/projects/{project}/solution-sections/{section_id}"
            "/versions")
    def headers(key):
        return {"cookie": "plm_session=" + token.hex(),
                "origin": "https://plm.example.test",
                "x-csrf-token": csrf.hex(),
                "idempotency-key": key}
    with TestClient(create_app(solution_section_version_validate_router=router),
                    base_url="https://plm.example.test") as app:
        old = app.post(f"{base}/{old_id}:validate",
                       headers=headers("section-old-fit-validate-0001"))
        assert old.status_code == 200, old.text
        assert old.json()["data"]["facts"]["spec"] == "UNAVAILABLE"
        first = app.post(f"{base}/{new_id}:validate",
                         headers=headers("section-new-fit-validate-0001"))
        assert first.status_code == 200, first.text
        data = first.json()["data"]
        assert data["facts"]["spec"] == "PASS", data
        assert data["valid"] and not data["ready_for_review"]
        assert app.post(f"{base}/{new_id}:validate",
                        headers=headers("section-new-fit-validate-0001"))\
            .json()["data"] == data
        # Disposable test DB: simulate a subsequently invalidated approval.
        with psycopg.connect(**connection) as database:
            database.execute("SET LOCAL session_replication_role='replica'")
            database.execute(
                "UPDATE plm.sol_structured_specs SET version_state='SUPERSEDED' "
                "WHERE structured_solution_spec_id=%s", (spec_id,))
            database.commit()
        invalidated = app.post(f"{base}/{new_id}:validate",
                               headers=headers("section-new-fit-validate-0002"))
        assert invalidated.status_code == 200, invalidated.text
        assert invalidated.json()["data"]["facts"]["spec"] == "UNAVAILABLE"
        assert not invalidated.json()["data"]["ready_for_review"]
        replay = app.post(f"{base}/{new_id}:validate",
                          headers=headers("section-new-fit-validate-0001"))
        assert replay.status_code == 200 and replay.json()["data"] == data
    print("SOL_05_A04_P12_P05_P03_SPEC_CURRENT_WINDOWS_PASS: approved fit "
          "Spec PASS, old NULL unavailable, invalidated current approval "
          "unavailable, first-observation replay")


if __name__ == "__main__":
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
