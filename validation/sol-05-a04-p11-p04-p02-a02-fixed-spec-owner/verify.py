"""Win11/PG18 real approved Spec -> atomic Section FIXED_REFS HTTP proof."""

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
    "qualified_spec_fixture",
    ROOT / "validation/sol-05-a04-p11-p04-p02-a01-spec-qualification/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
_qualified = prior._after_submit


def _after_submit(*, port, runtime, project, other_project, draft,
                  token, csrf, audit, license_guard, documents, downloads,
                  parse_results, **context):
    _qualified(
        port=port, runtime=runtime, project=project,
        other_project=other_project, draft=draft, token=token, csrf=csrf,
        audit=audit, license_guard=license_guard, documents=documents,
        downloads=downloads, parse_results=parse_results, **context)
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    # Existing UNDECLARED/NONE_REQUIRED history is a supported upgrade path.
    command.downgrade(cfg, "20261023_0179")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with runtime.unit_of_work() as tx:
        spec = prior.SqlAlchemySectionSpecCandidateRepository().get(
            tx, project_id=project,
            spec_id=draft.structured_solution_spec_id)
        assert spec is not None and spec.section_refs
        source_ref = spec.section_refs[0]
        source = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project,
            section_id=source_ref.solution_section_id,
            version_id=source_ref.solution_section_version_id)
        assert source is not None and source.requirement_refs
    section_id = source.solution_section_id
    malformed = uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as database:
        latest_no, latest_id = database.execute(
            "SELECT version_no,solution_section_version_id FROM "
            "plm.sol_section_versions WHERE solution_section_id=%s "
            "ORDER BY version_no DESC LIMIT 1", (section_id,)).fetchone()
        try:
            database.execute(
                "INSERT INTO plm.sol_section_versions "
                "(solution_section_version_id,solution_section_id,project_id,"
                "version_no,version_state,title,content_document_version_ref,"
                "content_fingerprint,assumptions,exclusions,"
                "declared_requirement_count,declared_evidence_count,"
                "spec_binding_state,declared_spec_count,"
                "supersedes_version_ref,created_by) VALUES "
                "(%s,%s,%s,%s,'DRAFT','Incomplete Spec set',%s,%s,"
                "'[]','[]',0,0,'FIXED_REFS',1,%s,%s)",
                (malformed, section_id, project, latest_no + 1,
                 source.content_document_version_ref, b"m" * 32,
                 latest_id, source.created_by))
            database.execute(
                "INSERT INTO plm.sol_section_version_create_results "
                "(solution_section_version_id,solution_section_id,project_id,"
                "version_no,title,content_document_version_ref,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,"
                "declared_requirement_count,declared_evidence_count,"
                "supersedes_version_ref,created_by,created_at) "
                "SELECT solution_section_version_id,solution_section_id,project_id,"
                "version_no,title,content_document_version_ref,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,"
                "declared_requirement_count,declared_evidence_count,"
                "supersedes_version_ref,created_by,created_at "
                "FROM plm.sol_section_versions WHERE solution_section_version_id=%s",
                (malformed,))
            database.commit()
        except psycopg.Error as error:
            assert "create set is incomplete" in str(error)
            database.rollback()
        else:
            raise AssertionError("incomplete fixed SpecRef set must not commit")
    payload = {
        "title": "Qualified specialist design revision",
        "content_document_version_ref": str(source.content_document_version_ref),
        "content_artifact_ref": None,
        "requirement_refs": [{
            "requirement_id": str(item.requirement_id),
            "requirement_version_id": str(item.requirement_version_id),
        } for item in source.requirement_refs],
        "evidence_ids": [str(item) for item in source.evidence_ids],
        "assumptions": list(source.assumptions),
        "exclusions": list(source.exclusions),
        "spec_binding_state": "FIXED_REFS",
        "spec_not_required_reason": None,
        "structured_spec_refs": [{
            "spec_series_id": str(spec.spec_series_id),
            "structured_solution_spec_id": str(spec.structured_solution_spec_id),
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
    def headers(session_token: bytes, csrf_token: bytes, key: str):
        return {
            "cookie": "plm_session=" + session_token.hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": csrf_token.hex(),
            "idempotency-key": key,
        }
    with TestClient(create_app(solution_section_version_create_router=router),
                    base_url="https://plm.example.test") as app:
        request_headers = headers(token, csrf, "section-approved-spec-0001")
        first = app.post(path, headers=request_headers, json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert "spec_binding_state" not in data
        assert app.post(path, headers=request_headers, json=payload).json()["data"] == data
        changed = {**payload, "structured_spec_refs": [{
            **payload["structured_spec_refs"][0],
            "structured_solution_spec_id": str(uuid.uuid4()),
        }]}
        assert app.post(path, headers=request_headers, json=changed).status_code == 409
        assert app.post(path, headers=headers(
            token, csrf, "section-invalid-spec-0001"), json=changed).status_code == 503
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=headers(token, csrf, "section-cross-spec-0001"),
                        json=payload).status_code == 404
    version_id = uuid.UUID(data["solution_section_version_id"])
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as database:
        row = database.execute(
            "SELECT spec_binding_state,declared_spec_count,content_fingerprint "
            "FROM plm.sol_section_versions WHERE solution_section_version_id=%s",
            (version_id,)).fetchone()
        assert row is not None and row[:2] == ("FIXED_REFS", 1)
        assert len(row[2]) == 32
        refs = database.execute(
            "SELECT spec_series_id,structured_solution_spec_id,ordinal "
            "FROM plm.sol_section_spec_refs WHERE solution_section_version_id=%s",
            (version_id,)).fetchall()
        assert refs == [(spec.spec_series_id, spec.structured_solution_spec_id, 1)]
        receipt = database.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_SECTION_VERSION_CREATE' AND result_ref_id=%s",
            (version_id,)).fetchone()[0]
        audit_count = database.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_SECTION_VERSION_CREATED' AND target_version_id=%s",
            (version_id,)).fetchone()[0]
        assert receipt == audit_count == 1
        try:
            database.execute(
                "INSERT INTO plm.sol_section_spec_refs "
                "(solution_section_version_id,solution_section_id,project_id,"
                "spec_series_id,structured_solution_spec_id,ordinal) "
                "VALUES (%s,%s,%s,%s,%s,2)",
                (version_id, section_id, project, spec.spec_series_id,
                 spec.structured_solution_spec_id))
        except psycopg.Error:
            database.rollback()
        else:
            raise AssertionError("committed SpecRef set must be sealed")
    with runtime.unit_of_work() as tx:
        view = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section_id,
            version_id=version_id)
        assert view is not None
        assert view.spec_binding_state == "FIXED_REFS"
        assert view.structured_spec_refs == (
            prior.SectionStructuredSpecRef(
                spec.spec_series_id, spec.structured_solution_spec_id),)
    try:
        command.downgrade(cfg, "20261023_0179")
    except RuntimeError as error:
        assert "Section SpecRef history prevents downgrade" in str(error)
    else:
        raise AssertionError("fixed SpecRef history must block downgrade")
    print("SOL_05_A04_P11_P04_P02_A02_FIXED_SPEC_OWNER_PASS: approved Spec "
          "HTTP201/replay/collision, qualified immutable PG refs, receipt/Audit, "
          "late insert/cross-project/wrong Spec/downgrade denied")


if __name__ == "__main__":
    prior._after_submit = _after_submit
    prior.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                prior._after_specs(created=created, **specs))))
