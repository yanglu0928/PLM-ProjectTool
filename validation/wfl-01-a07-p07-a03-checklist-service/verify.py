"""Win11/PostgreSQL 18 proof for the authorized Checklist command service."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification,
    HandoverWorkflowEvidenceObservation,
    HandoverWorkflowReviewObservation,
)
from plm_assistant.modules.handover.infrastructure.workflow_qualification_repository import (
    SqlAlchemyHandoverWorkflowQualificationRepository,
)
from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    RecordWorkflowChecklist, WorkflowChecklistRecordError,
    WorkflowChecklistRecordService,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.checklist_record_replay_repository import (
    SqlAlchemyChecklistRecordReplayRepository,
)


ROOT = Path(__file__).resolve().parents[2]
PORT = 55434
CSRF = b"c" * 32


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_01_a07_p07_a03_fixture",
)
insert, initialize, seed_evidence = (
    fixture.insert, fixture.initialize, fixture.seed_evidence,
)


def connect(name: str):
    return psycopg.connect(
        host="127.0.0.1", port=PORT, user="poc_admin",
        dbname=name, autocommit=True,
    )


def user(db, label: str, token: bytes) -> uuid.UUID:
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES(%s,%s) RETURNING user_id", (label, label.lower()),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES(%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,"
        "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
        (credential, user_id),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions"
        "(session_token_digest,csrf_digest,user_id,credential_version,"
        "idle_expires_at,absolute_expires_at) VALUES(%s,%s,%s,1,"
        "statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(),
         user_id),
    )
    return user_id


def start(db, workflow_id: uuid.UUID) -> None:
    with db.transaction():
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


class Guard:
    enabled = True

    def require_valid(self, **_kwargs):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class Qualification:
    def __init__(self, values):
        self.values = values

    def qualify_only_current_in_transaction(self, _tx, query):
        return self.values[(query.project_id, query.item_key)]


class FailingAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


def main() -> None:
    database = "wflservice3_" + uuid.uuid4().hex[:10]
    tokens = tuple(bytes([ord("s") + index]) * 32 for index in range(5))
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database),
        ))
        runtime = None
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=database,
            )
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            runtime = create_database_runtime(url)
            with connect(database) as db:
                managers = [user(db, f"Checklist Manager {index}", tokens[index])
                            for index in range(4)]
                member = user(db, "Checklist Member", tokens[4])
                projects, workflows, evidence_ids = [], [], []
                with db.transaction():
                    for index, manager in enumerate(managers):
                        project = insert(db, "prj_projects", dict(
                            project_code=f"WCSERVICE{index}",
                            project_code_normalized=f"wcservice{index}",
                            name=f"Synthetic Checklist service {index}",
                            created_by=manager,
                        ), "project_id")
                        department = insert(db, "prj_departments", dict(
                            project_id=project, department_code="D",
                            department_code_normalized="d", name="Department",
                        ), "department_id")
                        insert(db, "prj_project_members", dict(
                            project_id=project, user_id=manager,
                            department_id=department,
                            project_role="PROJECT_MANAGER",
                        ), "project_member_id")
                        if index == 0:
                            insert(db, "prj_project_members", dict(
                                project_id=project, user_id=member,
                                department_id=department,
                                project_role="IMPLEMENTATION_MEMBER",
                            ), "project_member_id")
                        workflows.append(initialize(db, project, manager))
                        projects.append(project)
                for workflow in workflows:
                    start(db, workflow)
                for project, manager in zip(projects, managers):
                    evidence_ids.append(seed_evidence(db, project, manager))
                qualifications = {}
                for project, evidence_id in zip(projects, evidence_ids):
                    state, version, fingerprint = db.execute(
                        "SELECT eligibility_state,lock_version,content_fingerprint "
                        "FROM plm.evd_evidence_records WHERE evidence_id=%s",
                        (evidence_id,),
                    ).fetchone()
                    assert state == "ELIGIBLE"
                    observed = HandoverWorkflowEvidenceObservation(
                        evidence_id, project, version, bytes(fingerprint),
                        datetime.now(timezone.utc),
                    )
                    review = HandoverWorkflowReviewObservation(
                        uuid.uuid4(), uuid.uuid4(), project, uuid.uuid4(),
                        uuid.uuid4(), 1, b"v" * 32,
                        datetime.now(timezone.utc),
                    )
                    for item_key in (
                        "HANDOVER_BASELINE", "HANDOVER_ISSUES",
                    ):
                        qualifications[(project, item_key)] = (
                            HandoverChecklistQualification(
                                item_key, project, review.subject_version_id,
                                b"q" * 32, (observed,), review,
                            )
                        )

            guard = Guard()
            base = dict(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(),
                projects=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                license_guard=guard,
                qualification=Qualification(qualifications),
                appender=SqlAlchemyChecklistRecordAppendRepository(),
                replay=SqlAlchemyChecklistRecordReplayRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            service = WorkflowChecklistRecordService(
                **base, audit=AuditService(SqlAlchemyAuditRepository()),
            )

            def request(index=0, *, token=None, result=ChecklistState.PASS,
                        version=1, evidence=None, item="HANDOVER_BASELINE"):
                refs = (evidence_ids[index],) if evidence is None else evidence
                if result is ChecklistState.FAIL:
                    refs = ()
                return RecordWorkflowChecklist(
                    tokens[index] if token is None else token, CSRF,
                    uuid.uuid4(), projects[index], item, result, refs, (),
                    version,
                )

            def denied(candidate, code, key, target=service):
                try:
                    target.record(candidate, idempotency_key=key)
                except WorkflowChecklistRecordError as error:
                    assert error.code == code, (error.code, code)
                else:
                    raise AssertionError(f"Checklist command accepted: {code}")

            denied(request(token=tokens[4]), "RESOURCE_NOT_FOUND",
                   "checklist-member-01")
            denied(request(evidence=(uuid.uuid4(),)),
                   "WORKFLOW_GATE_NOT_SATISFIED", "checklist-evidence-01")
            denied(request(result=ChecklistState.WAIVED),
                   "WORKFLOW_GATE_NOT_SATISFIED", "checklist-waived-001")
            guard.enabled = False
            denied(request(), "LICENSE_OPERATION_DENIED",
                   "checklist-license-01")
            guard.enabled = True

            key = "checklist-pass-key-001"
            first = service.record(request(), idempotency_key=key)
            replay = service.record(request(), idempotency_key=key)
            assert replay.record.record_id == first.record.record_id
            assert replay.record.result is ChecklistState.PASS
            denied(request(version=2), "CONFLICT_IDEMPOTENCY", key)

            corrected = service.record(
                request(result=ChecklistState.FAIL, version=2),
                idempotency_key="checklist-fail-key-001",
            )
            assert corrected.record.result is ChecklistState.FAIL
            historical = service.record(request(), idempotency_key=key)
            assert historical.record.record_id == first.record.record_id
            assert historical.record.result is ChecklistState.PASS
            assert historical.current_workflow_version == 3

            failing = WorkflowChecklistRecordService(
                **base, audit=FailingAudit(),
            )
            denied(request(1), "WORKFLOW_UNAVAILABLE",
                   "checklist-audit-key-1", target=failing)
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s", (projects[1],),
                ).fetchone()[0] == 0
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts "
                    "WHERE project_id=%s", (projects[1],),
                ).fetchone()[0] == 0

            def competing(_index):
                return service.record(
                    request(2), idempotency_key="checklist-concurrent-01",
                ).record.record_id

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(competing, range(2)))
            assert outcomes[0] == outcomes[1]

            selector = SqlAlchemyHandoverWorkflowQualificationRepository()
            with runtime.unit_of_work() as tx:
                assert selector.only_current_analysis_id(
                    tx, project_id=projects[3],
                ) is None
            candidate_ids = (uuid.uuid4(), uuid.uuid4())
            version_ids = (uuid.uuid4(), uuid.uuid4())
            with connect(database) as db:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.hnd_analyses"
                        "(handover_analysis_id,project_id,analysis_purpose,"
                        "source_set_ref,current_approved_version_ref,created_by) "
                        "VALUES(%s,%s,'Synthetic selector',%s,%s,%s)",
                        (candidate_ids[0], projects[3],
                         "sha256:" + "a" * 64, version_ids[0], managers[3]),
                    )
            with runtime.unit_of_work() as tx:
                assert selector.only_current_analysis_id(
                    tx, project_id=projects[3],
                ) == candidate_ids[0]
            with connect(database) as db:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.hnd_analyses"
                        "(handover_analysis_id,project_id,analysis_purpose,"
                        "source_set_ref,current_approved_version_ref,created_by) "
                        "VALUES(%s,%s,'Synthetic ambiguous',%s,%s,%s)",
                        (candidate_ids[1], projects[3],
                         "sha256:" + "b" * 64, version_ids[1], managers[3]),
                    )
            with runtime.unit_of_work() as tx:
                assert selector.only_current_analysis_id(
                    tx, project_id=projects[3],
                ) is None

            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s", (projects[0],),
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events "
                    "WHERE action='WORKFLOW_CHECKLIST_RECORDED'",
                ).fetchone()[0] == 3
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts "
                    "WHERE operation='V1_WORKFLOW_CHECKLIST_RECORD' "
                    "AND state='COMPLETED'",
                ).fetchone()[0] == 3
            print(
                "WFL_01_A07_P07_A03_CHECKLIST_SERVICE_PASS: real Session/"
                "CSRF/ProjectManager/License, exact owner Evidence, immutable "
                "original replay after correction, Audit rollback, concurrent "
                "same-key replay and zero/one/multiple Handover selector verified; "
                "qualification facts synthetic, no HTTP/Gate claim"
            )
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(
                sql.Identifier(database),
            ))


if __name__ == "__main__":
    main()
