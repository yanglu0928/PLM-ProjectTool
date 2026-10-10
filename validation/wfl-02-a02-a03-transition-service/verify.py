"""Win11/PostgreSQL proof for the authorized Handover Transition service."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.entrypoints.windows_workflow_checklist import (
    _create_handover_qualification,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
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
from plm_assistant.modules.workflow.application.transition_stage import (
    TransitionWorkflowStage, WorkflowStageTransitionError,
    WorkflowStageTransitionService,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.checklist_record_replay_repository import (
    SqlAlchemyChecklistRecordReplayRepository,
)
from plm_assistant.modules.workflow.infrastructure.stage_transition_repository import (
    SqlAlchemyStageTransitionRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handover = load(
    ROOT / "validation/hnd-03-a04-workflow-qualification-pg/verify.py",
    "wfl_02_a02_a03_handover_fixture",
)
workflow = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_02_a02_a03_workflow_fixture",
)


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic transition audit failure")


def verify_service(context: dict[str, object]) -> None:
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
    projects = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work, repository=project_repository,
    )
    receipts = SqlAlchemyIdempotencyReceipts()
    checklist = WorkflowChecklistRecordService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=projects,
        license_guard=context["license_guard"],
        qualification=qualification,
        appender=SqlAlchemyChecklistRecordAppendRepository(),
        replay=SqlAlchemyChecklistRecordReplayRepository(),
        receipts=receipts, audit=context["audit"],
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
        current = checklist.record(
            RecordWorkflowChecklist(
                token, handover.CSRF, trace_id, project_id, item_key,
                ChecklistState.PASS,
                tuple(value.evidence_id for value in qualified.evidence),
                (), expected_version,
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        assert current.record.item_key == item_key
        assert current.record.result is ChecklistState.PASS

    command = TransitionWorkflowStage(
        token, handover.CSRF, uuid.uuid4(), project_id,
        "SURVEY", 3, "Handover evidence accepted",
    )
    failed = WorkflowStageTransitionService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=projects,
        license_guard=context["license_guard"],
        qualification=qualification,
        transitions=SqlAlchemyStageTransitionRepository(),
        receipts=receipts, audit=FailingAudit(),
    )
    try:
        failed.transition(command, idempotency_key=str(uuid.uuid4()))
    except WorkflowStageTransitionError as error:
        assert error.code == "WORKFLOW_UNAVAILABLE"
    else:
        raise AssertionError("transition survived Audit failure")
    with handover.connect(database) as db:
        assert db.execute(
            "SELECT current_stage_key,lock_version FROM "
            "plm.wfl_project_workflows WHERE project_id=%s",
            (project_id,),
        ).fetchone() == ("HANDOVER", 3)
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_stage_transitions "
            "WHERE project_id=%s", (project_id,),
        ).fetchone()[0] == 0

    transitions = WorkflowStageTransitionService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=projects,
        license_guard=context["license_guard"],
        qualification=qualification,
        transitions=SqlAlchemyStageTransitionRepository(),
        receipts=receipts, audit=context["audit"],
    )
    key = str(uuid.uuid4())
    first = transitions.transition(command, idempotency_key=key)
    replay = transitions.transition(command, idempotency_key=key)
    assert replay.stage_transition_id == first.stage_transition_id
    assert replay.snapshot == first.snapshot
    assert first.snapshot.workflow_id == workflow_id
    assert first.snapshot.from_stage == "HANDOVER"
    assert first.snapshot.to_stage == "SURVEY"
    assert first.snapshot.before_lock_version == 3
    assert first.snapshot.after_lock_version == 4
    assert tuple(value.snapshot.item_key for value in first.gates) == (
        "HANDOVER_BASELINE", "HANDOVER_ISSUES",
    )

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
    handover.main(verify_service)
    print(
        "WFL_02_A02_A03_TRANSITION_SERVICE_PG_PASS: real current Handover "
        "Owner, Session/CSRF, ProjectManager, License, both current Checklist "
        "PASS records, atomic Transition/Audit/receipt and exact replay verified"
    )


if __name__ == "__main__":
    main()
