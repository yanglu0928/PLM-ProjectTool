"""Disposable Win11/PG18 approved Spec -> Section fit rationale Owner proof."""

from __future__ import annotations

import importlib.util
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
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "fit_owner_fixed_spec_fixture",
    ROOT / "validation/sol-05-a04-p11-p04-p02-a02-fixed-spec-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
fixture = prior.prior
_fixed_owner = prior._after_submit


def _after_submit(*, port, runtime, project, draft, token, csrf, audit,
                  license_guard, documents, downloads, parse_results, **context):
    _fixed_owner(
        port=port, runtime=runtime, project=project, draft=draft,
        token=token, csrf=csrf, audit=audit, license_guard=license_guard,
        documents=documents, downloads=downloads,
        parse_results=parse_results, **context)
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres")
    with psycopg.connect(**connection) as database:
        old_id, section_id = database.execute(
            "SELECT solution_section_version_id,solution_section_id FROM "
            "plm.sol_section_versions WHERE project_id=%s AND "
            "spec_binding_state='FIXED_REFS' ORDER BY created_at DESC LIMIT 1",
            (project,)).fetchone()
    with runtime.unit_of_work() as tx:
        old = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section_id, version_id=old_id)
        assert old is not None and len(old.structured_spec_refs) == 1
        assert old.structured_spec_refs[0].fit_rationale is None
    payload = {
        "title": "Qualified specialist design with fit basis",
        "content_document_version_ref": str(old.content_document_version_ref),
        "content_artifact_ref": None,
        "requirement_refs": [{
            "requirement_id": str(item.requirement_id),
            "requirement_version_id": str(item.requirement_version_id),
        } for item in old.requirement_refs],
        "evidence_ids": [str(item) for item in old.evidence_ids],
        "assumptions": list(old.assumptions),
        "exclusions": list(old.exclusions),
        "spec_binding_state": "FIXED_REFS",
        "spec_not_required_reason": None,
        "structured_spec_refs": [{
            "spec_series_id": str(old.structured_spec_refs[0].spec_series_id),
            "structured_solution_spec_id": str(
                old.structured_spec_refs[0].structured_solution_spec_id),
            "fit_rationale": "Author confirms this specialist design fits the revision",
        }],
    }
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_version_create_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    path = (f"/api/v1/projects/{project}/solution-sections/"
            f"{section_id}/versions")
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test",
               "x-csrf-token": csrf.hex(),
               "idempotency-key": "section-fit-owner-0001"}
    with TestClient(create_app(solution_section_version_create_router=router),
                    base_url="https://plm.example.test") as app:
        first = app.post(path, headers=headers, json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert "fit_rationale" not in data
        replay = app.post(path, headers=headers, json=payload)
        assert replay.status_code == 201 and replay.json()["data"] == data
        altered = {**payload, "structured_spec_refs": [{
            **payload["structured_spec_refs"][0],
            "fit_rationale": "A different author claim"}]}
        assert app.post(path, headers=headers, json=altered).status_code == 409
        malformed = {**payload, "structured_spec_refs": [{
            **payload["structured_spec_refs"][0], "fit_rationale": " "}]}
        assert app.post(path, headers={**headers, "idempotency-key":
                        "section-fit-owner-bad"}, json=malformed).status_code == 422
    version_id = uuid.UUID(data["solution_section_version_id"])
    with psycopg.connect(**connection) as database:
        ref = database.execute(
            "SELECT fit_rationale FROM plm.sol_section_spec_refs "
            "WHERE solution_section_version_id=%s", (version_id,)).fetchone()
        assert ref == (payload["structured_spec_refs"][0]["fit_rationale"],)
        receipt = database.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_SECTION_VERSION_CREATE' AND result_ref_id=%s",
            (version_id,)).fetchone()[0]
        event = database.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_SECTION_VERSION_CREATED' AND target_version_id=%s",
            (version_id,)).fetchone()[0]
        assert receipt == event == 1
    with runtime.unit_of_work() as tx:
        view = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section_id, version_id=version_id)
        assert view is not None
        assert view.structured_spec_refs[0].fit_rationale == ref[0]
    try:
        command.downgrade(cfg, "20261023_0181")
    except RuntimeError as error:
        assert "fit history prevents Owner downgrade" in str(error)
    else:
        raise AssertionError("non-null fit history must block downgrade")
    print("SOL_05_A04_P12_P04_P02_FIT_OWNER_PASS: Win11/PG18 HTTP201, "
          "replay/409, database/history, receipt/Audit and downgrade closure")


if __name__ == "__main__":
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
