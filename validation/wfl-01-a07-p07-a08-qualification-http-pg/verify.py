"""Win11/PostgreSQL proof of Checklist qualification preview composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_qualification_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import (
    SqlAlchemyPasswordIssueAccess,
)
from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ScryptPasswordHasher,
)
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.document.application.read_parse_result import (
    DocumentParseResultReadService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://localhost"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handover = load(
    ROOT / "validation/hnd-03-a04-workflow-qualification-pg/verify.py",
    "wfl_01_a07_p07_a08_handover_fixture",
)
workflow = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_01_a07_p07_a08_workflow_fixture",
)


def verify_http(context: dict[str, object]) -> None:
    runtime = context["runtime"]
    database = context["database"]
    project_id = context["project_id"]
    manager_id = context["manager_id"]
    token = context["manager_token"]
    evidence_ids = context["evidence_ids"]
    assert isinstance(database, str)
    assert isinstance(project_id, uuid.UUID)
    assert isinstance(manager_id, uuid.UUID)
    assert isinstance(token, bytes)
    assert isinstance(evidence_ids, tuple) and evidence_ids

    with handover.connect(database) as db, db.transaction():
        workflow_id = workflow.initialize(db, project_id, manager_id)
        db.execute(
            "UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',"
            "current_stage_key='HANDOVER',lock_version=1,"
            "updated_at=statement_timestamp() WHERE workflow_id=%s",
            (workflow_id,),
        )
        db.execute(
            "UPDATE plm.wfl_stages SET stage_state='ACTIVE' "
            "WHERE workflow_id=%s AND stage_key='HANDOVER'",
            (workflow_id,),
        )

    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
        audit=context["audit"],
        idempotency=SqlAlchemyIdempotencyReceipts(),
    )
    parse_results = DocumentParseResultReadService(
        documents=context["downloads"],
        metadata=SqlAlchemyParseResultReadRepository(),
        storage=LocalParseResultStorage(context["data_root"]),
        unit_of_work=runtime.unit_of_work,
    )
    router = create_windows_workflow_checklist_qualification_router(
        runtime,
        sessions=sessions,
        origins=LoginOriginPolicy([ORIGIN]),
        license_guard=context["license_guard"],
        documents=context["documents"],
        downloads=context["downloads"],
        parse_results=parse_results,
    )
    path = (
        f"/api/v1/projects/{project_id}/workflow/checklist-items/"
        "HANDOVER_ISSUES/qualification"
    )
    headers = {"cookie": "plm_session=" + token.hex()}
    with TestClient(create_app(), base_url=ORIGIN) as disabled:
        assert disabled.get(path, headers=headers).status_code == 404
    with TestClient(
        create_app(workflow_checklist_qualification_router=router),
        base_url=ORIGIN,
    ) as client:
        anonymous = client.get(path)
        assert anonymous.status_code == 401, anonymous.text
        query_rejected = client.get(path + "?detail=true", headers=headers)
        assert query_rejected.status_code == 400, query_rejected.text
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data == {
            "workflow_id": str(workflow_id),
            "project_id": str(project_id),
            "definition_version": 1,
            "stage_key": "HANDOVER",
            "item_key": "HANDOVER_ISSUES",
            "current_item_state": "PENDING",
            "workflow_etag": '"v1"',
            "handover_analysis_version_id": data["handover_analysis_version_id"],
            "review_round_ref": data["review_round_ref"],
            "evidence_refs": [str(value) for value in evidence_ids],
        }
        uuid.UUID(data["handover_analysis_version_id"])
        uuid.UUID(data["review_round_ref"])
        assert response.headers["etag"] == '"v1"'
        assert response.headers["cache-control"] == "no-store"


def main() -> None:
    handover.main(verify_http)
    print(
        "WFL_01_A07_P07_A08_WINDOWS_QUALIFICATION_HTTP_PG_PASS: "
        "write-only Windows platform composition, default-disabled route, "
        "Session/Host/query rejection, real current Handover qualification, "
        "minimal response, strong ETag, no-store and read-only PostgreSQL "
        "snapshot verified"
    )


if __name__ == "__main__":
    main()
