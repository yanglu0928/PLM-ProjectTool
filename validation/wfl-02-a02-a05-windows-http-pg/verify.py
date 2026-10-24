"""Win11/PostgreSQL proof for production Stage Transition HTTP composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    _create_handover_qualification,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import (
    SqlAlchemyPasswordIssueAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
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
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowCurrentQualificationQuery,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    RecordWorkflowChecklist, WorkflowChecklistRecordService,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.checklist_record_replay_repository import (
    SqlAlchemyChecklistRecordReplayRepository,
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
    "wfl_02_a02_a05_handover_fixture",
)
workflow = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_02_a02_a05_workflow_fixture",
)


def verify_http(context: dict[str, object]) -> None:
    runtime = context["runtime"]
    database = context["database"]
    project_id = context["project_id"]
    manager_id = context["manager_id"]
    token = context["manager_token"]
    assert isinstance(database, str)
    assert isinstance(project_id, uuid.UUID)
    assert isinstance(manager_id, uuid.UUID)
    assert isinstance(token, bytes)

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
    qualification = _create_handover_qualification(
        documents=context["documents"], downloads=context["downloads"],
        parse_results=parse_results,
    )
    project_repository = SqlAlchemyProjectAuthorizationRepository()
    checklist = WorkflowChecklistRecordService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(),
        projects=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=project_repository,
        ),
        license_guard=context["license_guard"],
        qualification=qualification,
        appender=SqlAlchemyChecklistRecordAppendRepository(),
        replay=SqlAlchemyChecklistRecordReplayRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=context["audit"],
    )
    for expected_version, item_key in enumerate((
            "HANDOVER_BASELINE", "HANDOVER_ISSUES"), start=1):
        trace_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            qualified = qualification.qualify_only_current_in_transaction(
                tx, HandoverWorkflowCurrentQualificationQuery(
                    token, trace_id, project_id, item_key,
                ),
            )
        checklist.record(
            RecordWorkflowChecklist(
                token, handover.CSRF, trace_id, project_id, item_key,
                ChecklistState.PASS,
                tuple(value.evidence_id for value in qualified.evidence),
                (), expected_version,
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    router = create_windows_workflow_stage_transition_router(
        runtime, sessions=sessions, origins=LoginOriginPolicy([ORIGIN]),
        license_guard=context["license_guard"], audit=context["audit"],
        documents=context["documents"], downloads=context["downloads"],
        parse_results=parse_results,
    )
    path = f"/api/v1/projects/{project_id}/workflow:transition"
    key = str(uuid.uuid4())
    headers = {
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": handover.CSRF.hex(),
        "origin": ORIGIN,
        "idempotency-key": key,
        "if-match": '"v3"',
    }
    body = {
        "target_stage_key": "SURVEY",
        "reason": "Handover evidence accepted",
        "gate_snapshot_refs": [],
    }
    with TestClient(create_app(), base_url=ORIGIN) as disabled:
        assert disabled.post(path, json=body, headers=headers).status_code == 404
    with TestClient(
        create_app(workflow_transition_router=router), base_url=ORIGIN,
    ) as client:
        wrong_origin = client.post(
            path, json=body, headers={**headers, "origin": "http://invalid"},
        )
        assert wrong_origin.status_code == 403, wrong_origin.text
        client_supplied_gate = client.post(
            path,
            json={**body, "gate_snapshot_refs": [str(uuid.uuid4())]},
            headers={**headers, "idempotency-key": str(uuid.uuid4())},
        )
        assert client_supplied_gate.status_code == 422, client_supplied_gate.text
        first = client.post(path, json=body, headers=headers)
        assert first.status_code == 200, first.text
        data = first.json()["data"]
        assert data["workflow_id"] == str(workflow_id)
        assert data["project_id"] == str(project_id)
        assert data["from_stage"] == "HANDOVER"
        assert data["to_stage"] == "SURVEY"
        assert data["before_workflow_version"] == 3
        assert data["transitioned_workflow_version"] == 4
        assert data["current_workflow_version"] == 4
        assert data["etag"] == '"v4"'
        assert first.headers["etag"] == '"v4"'
        replay = client.post(path, json=body, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == data

    with handover.connect(database) as db:
        assert db.execute(
            "SELECT current_stage_key,lock_version FROM "
            "plm.wfl_project_workflows WHERE project_id=%s",
            (project_id,),
        ).fetchone() == ("SURVEY", 4)
        assert db.execute(
            "SELECT stage_key,stage_state FROM plm.wfl_stages "
            "WHERE project_id=%s AND stage_key IN ('HANDOVER','SURVEY') "
            "ORDER BY stage_order", (project_id,),
        ).fetchall() == [("HANDOVER", "COMPLETED"), ("SURVEY", "ACTIVE")]
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_stage_transitions "
            "WHERE project_id=%s", (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_transition_gate_items "
            "WHERE project_id=%s", (project_id,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE target_project_id=%s "
            "AND action='WORKFLOW_STAGE_TRANSITIONED'",
            (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE project_id=%s AND operation='V1_WORKFLOW_TRANSITION' "
            "AND state='COMPLETED'", (project_id,),
        ).fetchone()[0] == 1


def main() -> None:
    handover.main(verify_http)
    print(
        "WFL_02_A02_A05_WINDOWS_HTTP_PG_PASS: explicit Windows write "
        "composition, default-closed route, Origin/Session/CSRF/If-Match, "
        "server-owned Handover gates, PostgreSQL Transition/Audit/receipt "
        "and exact HTTP replay verified"
    )


if __name__ == "__main__":
    main()
