"""Win11/PostgreSQL proof of production Checklist HTTP composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_record_router,
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
CSRF = b"c" * 32


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handover = load(
    ROOT / "validation/hnd-03-a04-workflow-qualification-pg/verify.py",
    "wfl_01_a07_p07_a05_handover_fixture",
)
workflow = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_01_a07_p07_a05_workflow_fixture",
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
    router = create_windows_workflow_checklist_record_router(
        runtime,
        sessions=sessions,
        origins=LoginOriginPolicy([ORIGIN]),
        license_guard=context["license_guard"],
        audit=context["audit"],
        documents=context["documents"],
        downloads=context["downloads"],
        parse_results=parse_results,
    )
    path = (
        f"/api/v1/projects/{project_id}/workflow/checklist-items/"
        "HANDOVER_ISSUES:record"
    )
    key = str(uuid.uuid4())
    headers = {
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": CSRF.hex(),
        "origin": ORIGIN,
        "idempotency-key": key,
        "if-match": '"v1"',
    }
    body = {
        "result": "PASS",
        "evidence_refs": [str(value) for value in evidence_ids],
        "exception_refs": [],
        "reason": None,
        "impact": None,
    }
    with TestClient(create_app(), base_url=ORIGIN) as disabled:
        assert disabled.post(path, json=body, headers=headers).status_code == 404
    with TestClient(
        create_app(workflow_checklist_record_router=router), base_url=ORIGIN,
    ) as client:
        wrong_origin = client.post(
            path, json=body, headers={**headers, "origin": "http://invalid"},
        )
        assert wrong_origin.status_code == 403, wrong_origin.text
        first = client.post(path, json=body, headers=headers)
        assert first.status_code == 200, first.text
        data = first.json()["data"]
        assert data["result"] == "PASS"
        assert data["item_key"] == "HANDOVER_ISSUES"
        assert data["recorded_workflow_version"] == 2
        assert data["current_workflow_version"] == 2
        assert first.headers["etag"] == '"v2"'
        replay = client.post(path, json=body, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == data

    with handover.connect(database) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_checklist_records "
            "WHERE project_id=%s AND item_key='HANDOVER_ISSUES'",
            (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE target_project_id=%s "
            "AND action='WORKFLOW_CHECKLIST_RECORDED'",
            (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE project_id=%s AND operation='V1_WORKFLOW_CHECKLIST_RECORD' "
            "AND state='COMPLETED'",
            (project_id,),
        ).fetchone()[0] == 1


def main() -> None:
    handover.main(verify_http)
    print(
        "WFL_01_A07_P07_A05_WINDOWS_HTTP_PG_PASS: production Windows "
        "composition, disabled-by-default route, Origin/Session/CSRF/If-Match, "
        "real current Handover qualification, PostgreSQL append/Audit/receipt "
        "and exact HTTP replay verified"
    )


if __name__ == "__main__":
    main()
