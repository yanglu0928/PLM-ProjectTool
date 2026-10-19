"""Win11 real ASGI/PostgreSQL proof for SOL-06 VALIDATE composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_structured_spec_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_current_facts_for_windows_validation",
    ROOT / "validation/sol-06-a13-p04-structured-spec-current-facts/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _DeniedLicense:
    def require_valid(self, **_kwargs):
        from plm_assistant.modules.license.application.runtime_guard import (
            RuntimeLicenseError,
        )
        raise RuntimeLicenseError("EXPIRED")


def headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def on_http(
    *, port, runtime, project, other_project, token, csrf, member_token,
    member_csrf, first, second, evidence, audit, license_guard,
    documents, downloads, parse_results, **_unused,
) -> None:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    dependencies = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads, parse_results=parse_results)
    try:
        create_windows_structured_spec_validate_router(
            **{**dependencies, "documents": None})
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing Document proof dependency mounted VALIDATE")
    router = create_windows_structured_spec_validate_router(**dependencies)
    current_path = (
        f"/api/v1/projects/{project}/structured-solution-specs/"
        f"{second.structured_solution_spec_id}:validate")
    historical_path = (
        f"/api/v1/projects/{project}/structured-solution-specs/"
        f"{first.structured_solution_spec_id}:validate")

    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-closed-0001")
        ).status_code == 404
    with TestClient(create_app(
            solution_structured_spec_validate_router=router),
            base_url="https://plm.example.test") as application:
        response = application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-first-0001"))
        assert response.status_code == 200, response.text
        first_data = response.json()["data"]
        assert first_data["facts"] == {
            "integrity": "PASS", "payload": "PASS",
            "requirements": "PASS", "sections": "PASS",
            "evidence": "PASS", "artifacts": "PASS",
            "trace": "FAIL", "current_version": "PASS"}
        assert first_data["type_checks"][0] == {
            "code": "SCOPE_MAPPING", "status": "PASS"}
        assert first_data["valid"] and not first_data["ready_for_review"]
        assert response.headers["cache-control"] == "no-store"
        replay = application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-first-0001"))
        assert replay.status_code == 200
        assert replay.json()["data"] == first_data
        assert replay.json()["trace_id"] != response.json()["trace_id"]
        assert replay.headers["x-trace-id"] == replay.json()["trace_id"]

        assert application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-body-0001"),
            json={}).status_code == 400
        assert application.post(
            current_path + "?force=true",
            headers=headers(token, csrf, "structured-validate-query-0001")
        ).status_code == 400
        assert application.post(
            current_path.replace(str(project), str(other_project)),
            headers=headers(token, csrf, "structured-validate-other-0001")
        ).status_code == 404
        assert application.post(
            current_path,
            headers=headers(token, b"x" * 32,
                            "structured-validate-csrf-0001")
        ).status_code == 403
        wrong_origin = headers(
            token, csrf, "structured-validate-origin-0001")
        wrong_origin["origin"] = "https://evil.test"
        assert application.post(
            current_path, headers=wrong_origin).status_code == 403

        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as database:
            database.execute(
                "UPDATE plm.evd_evidence_records "
                "SET eligibility_state='INELIGIBLE', lock_version=lock_version+1 "
                "WHERE evidence_id=%s", (evidence,))
        drift = application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-drift-0001"))
        assert drift.status_code == 200, drift.text
        drift_data = drift.json()["data"]
        assert drift_data["facts"]["evidence"] == "UNAVAILABLE"
        assert drift_data["facts"]["integrity"] == "UNAVAILABLE"
        assert not drift_data["valid"] and not drift_data["ready_for_review"]
        assert application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-first-0001")
        ).json()["data"] == first_data

        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as database:
            database.execute(
                "UPDATE plm.evd_evidence_records "
                "SET eligibility_state='ELIGIBLE', lock_version=lock_version+1 "
                "WHERE evidence_id=%s", (evidence,))
        member = application.post(
            current_path, headers=headers(
                member_token, member_csrf,
                "structured-validate-member-0001"))
        assert member.status_code == 200, member.text
        assert member.json()["data"]["facts"]["evidence"] == "PASS"
        assert member.json()["data"]["facts"]["integrity"] == "FAIL"
        assert not member.json()["data"]["valid"]
        historical = application.post(
            historical_path,
            headers=headers(token, csrf,
                            "structured-validate-history-0001"))
        assert historical.status_code == 200, historical.text
        assert historical.json()["data"]["facts"]["current_version"] == "FAIL"
        assert not historical.json()["data"]["ready_for_review"]

    denied = create_windows_structured_spec_validate_router(
        **{**dependencies, "license_guard": _DeniedLicense()})
    with TestClient(create_app(
            solution_structured_spec_validate_router=denied),
            base_url="https://plm.example.test") as application:
        assert application.post(
            current_path,
            headers=headers(token, csrf, "structured-validate-license-0001")
        ).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as database:
        assert database.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_STRUCTURED_SPEC_VALIDATE'"
        ).fetchone()[0] == 4
        assert database.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_STRUCTURED_SPEC_VALIDATED'"
        ).fetchone()[0] == 4
    print("SOL_06_A13_P07_VALIDATE_WINDOWS_HTTP_PG_PASS: explicit write-mode "
          "composition, real Session/License/sources/PG, first/replay/drift, "
          "manager/member/history/isolation and strict empty HTTP request")


def after_specs(*, created: dict[str, object], **specs) -> None:
    shared = dict(
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"])
    prior.on_current_facts(**specs, **shared)
    on_http(
        **specs, **shared, csrf=created["csrf"],
        member_csrf=created["member_csrf"], audit=created["audit"],
        license_guard=created["license_guard"], evidence=created["evidence"])


if __name__ == "__main__":
    prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created: prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
