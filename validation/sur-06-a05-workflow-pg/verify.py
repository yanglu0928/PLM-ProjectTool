"""Windows 11/PostgreSQL 18.6 proof for Survey Workflow gates."""

from __future__ import annotations

import importlib.util
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    _create_qualification_registry,
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
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
from plm_assistant.modules.document.application.prepare_download import (
    VerifiedDownload,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    CurrentChecklistQualificationQuery,
)


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://localhost"
CSRF = b"c" * 32
ITEMS = ("SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review_fixture = load(
    ROOT / "validation/sur-04-a06-conclusion-review/verify.py",
    "sur06a05_review_fixture",
)
workflow_fixture = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "sur06a05_workflow_fixture",
)


class Documents:
    def __init__(self, facts) -> None:
        self.facts = facts

    def get_source_facts_for_evidence(
        self, transaction, query, document_id, document_version_id,
    ):
        assert self.facts.document_id == document_id
        assert self.facts.document_version_id == document_version_id
        return self.facts


class Downloads:
    def __init__(self, facts) -> None:
        self.facts = facts

    def prepare_in_transaction(
        self, transaction, query, document_id, document_version_id,
    ) -> VerifiedDownload:
        assert self.facts.document_id == document_id
        assert self.facts.document_version_id == document_version_id
        return VerifiedDownload(
            document_version_id, 0, "application/octet-stream",
            bytes.fromhex(self.facts.content_sha256), io.BytesIO(b""),
        )


class NoParse:
    def read(self, *args, **kwargs):
        raise AssertionError("whole-document Evidence must not read parse bytes")


def set_evidence_state(context, state: str, *, restore: bool = False) -> None:
    with review_fixture.schema.connect(context["database"]) as db, db.transaction():
        if restore:
            db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.evd_evidence_records SET eligibility_state=%s,"
            "eligibility_reason=%s,updated_by=%s,"
            "updated_at=statement_timestamp(),lock_version=%s "
            "WHERE evidence_id=%s",
            (
                state, "restored" if restore else "SUR-06-A05 drift",
                context["manager_id"], 0 if restore else 1,
                context["evidence_id"],
            ),
        )


def verify_workflow(context: dict[str, object]) -> None:
    database = context["database"]
    runtime = context["runtime"]
    project = context["project_id"]
    manager = context["manager_id"]
    token = context["manager_token"]
    documents = Documents(context["document_facts"])
    downloads = Downloads(context["document_facts"])
    parse_results = NoParse()

    with review_fixture.schema.connect(database) as db, db.transaction():
        workflow_id = workflow_fixture.initialize(db, project, manager)
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',"
            "current_stage_key='SURVEY',lock_version=4,"
            "updated_at=statement_timestamp() WHERE workflow_id=%s",
            (workflow_id,),
        )
        db.execute(
            "UPDATE plm.wfl_stages SET stage_state=CASE "
            "WHEN stage_key='HANDOVER' THEN 'COMPLETED' "
            "WHEN stage_key='SURVEY' THEN 'ACTIVE' ELSE 'NOT_STARTED' END "
            "WHERE workflow_id=%s", (workflow_id,),
        )
        db.execute(
            "UPDATE plm.wfl_checklist_items SET item_state='PASS',lock_version=1 "
            "WHERE workflow_id=%s AND item_key LIKE 'HANDOVER_%%'",
            (workflow_id,),
        )

    registry = _create_qualification_registry(
        documents=documents, downloads=downloads,
        parse_results=parse_results,
    )
    qualified = {}
    with runtime.unit_of_work() as tx:
        for item_key in ITEMS:
            value = registry.qualify_only_current_in_transaction(
                tx, CurrentChecklistQualificationQuery(
                    token, uuid.uuid4(), project, item_key,
                ),
            )
            qualified[item_key] = value
        assert len({value.coherence_key for value in qualified.values()}) == 1
        assert all(
            tuple(item.evidence_id for item in value.evidence)
            == (context["evidence_id"],)
            for value in qualified.values()
        )
        with review_fixture.schema.connect(database) as rival:
            for table, identity, value in (
                ("srv_conclusions", "survey_conclusion_id",
                 context["survey_conclusion_id"]),
                ("evd_evidence_records", "evidence_id",
                 context["evidence_id"]),
                ("rvw_review_rounds", "review_round_id",
                 context["review_round_id"]),
            ):
                try:
                    rival.execute(
                        f"SELECT 1 FROM plm.{table} WHERE {identity}=%s "
                        "FOR UPDATE NOWAIT", (value,),
                    )
                except Exception as error:
                    assert getattr(error, "sqlstate", None) == "55P03", (
                        table, getattr(error, "sqlstate", None),
                    )
                    rival.rollback()
                else:
                    raise AssertionError(f"qualification did not lock {table}")

    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
        audit=context["audit"],
        idempotency=SqlAlchemyIdempotencyReceipts(),
    )
    origins = LoginOriginPolicy([ORIGIN])
    qualification_router = create_windows_workflow_checklist_qualification_router(
        runtime, sessions=sessions, origins=origins,
        license_guard=context["guard"], documents=documents,
        downloads=downloads, parse_results=parse_results,
    )
    record_router = create_windows_workflow_checklist_record_router(
        runtime, sessions=sessions, origins=origins,
        license_guard=context["guard"], audit=context["audit"],
        documents=documents, downloads=downloads,
        parse_results=parse_results,
    )
    transition_router = create_windows_workflow_stage_transition_router(
        runtime, sessions=sessions, origins=origins,
        license_guard=context["guard"], audit=context["audit"],
        documents=documents, downloads=downloads,
        parse_results=parse_results,
    )
    app = create_app(
        workflow_checklist_qualification_router=qualification_router,
        workflow_checklist_record_router=record_router,
        workflow_transition_router=transition_router,
    )
    cookie = "plm_session=" + token.hex()
    get_headers = {"cookie": cookie, "host": "localhost"}
    write_headers = {
        "cookie": cookie, "x-csrf-token": CSRF.hex(), "origin": ORIGIN,
    }

    def qualification(client, item_key):
        response = client.get(
            f"/api/v1/projects/{project}/workflow/checklist-items/"
            f"{item_key}/qualification", headers=get_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["stage_key"] == "SURVEY"
        assert data["survey_conclusion_id"] == str(
            context["survey_conclusion_id"],
        )
        assert "handover_analysis_version_id" not in data
        return data

    with TestClient(app, base_url=ORIGIN) as client:
        previews = {item: qualification(client, item) for item in ITEMS}
        set_evidence_state(context, "INELIGIBLE")
        drift = client.post(
            f"/api/v1/projects/{project}/workflow/checklist-items/"
            f"{ITEMS[0]}:record",
            headers={**write_headers, "idempotency-key": str(uuid.uuid4()),
                     "if-match": '"v4"'},
            json={
                "result": "PASS", "reason": "Synthetic current fact",
                "impact": "Validation only",
                "evidence_refs": previews[ITEMS[0]]["evidence_refs"],
                "exception_refs": [],
            },
        )
        assert drift.status_code == 409, drift.text
        assert drift.json()["error"]["code"] == "WORKFLOW_GATE_NOT_SATISFIED"
        set_evidence_state(context, "ELIGIBLE", restore=True)

    barrier = Barrier(2)

    def concurrent_record(item_key):
        barrier.wait()
        with TestClient(app, base_url=ORIGIN) as client:
            return client.post(
                f"/api/v1/projects/{project}/workflow/checklist-items/"
                f"{item_key}:record",
                headers={
                    **write_headers,
                    "idempotency-key": str(uuid.uuid4()),
                    "if-match": '"v4"',
                },
                json={
                    "result": "PASS", "reason": "Concurrent synthetic gate",
                    "impact": "Validation only",
                    "evidence_refs": previews[item_key]["evidence_refs"],
                    "exception_refs": [],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = tuple(pool.map(concurrent_record, ITEMS))
    statuses = tuple(response.status_code for response in responses)
    assert sorted(statuses) == [200, 409], (
        statuses, tuple(response.text for response in responses),
    )
    loser = ITEMS[statuses.index(409)]
    with TestClient(app, base_url=ORIGIN) as client:
        retried = client.post(
            f"/api/v1/projects/{project}/workflow/checklist-items/{loser}:record",
            headers={
                **write_headers,
                "idempotency-key": str(uuid.uuid4()), "if-match": '"v5"',
            },
            json={
                "result": "PASS", "reason": "Retry after version fence",
                "impact": "Validation only",
                "evidence_refs": previews[loser]["evidence_refs"],
                "exception_refs": [],
            },
        )
        assert retried.status_code == 200, retried.text
        assert retried.headers["etag"] == '"v6"'

        transition_path = f"/api/v1/projects/{project}/workflow:transition"
        transition_body = {
            "target_stage_key": "REQUIREMENT",
            "reason": "Synthetic Survey gates accepted",
            "gate_snapshot_refs": [],
        }
        set_evidence_state(context, "INELIGIBLE")
        drifted_transition = client.post(
            transition_path,
            headers={
                **write_headers,
                "idempotency-key": str(uuid.uuid4()), "if-match": '"v6"',
            },
            json=transition_body,
        )
        assert drifted_transition.status_code == 409, drifted_transition.text
        assert drifted_transition.json()["error"]["code"] \
            == "WORKFLOW_GATE_NOT_SATISFIED"
        set_evidence_state(context, "ELIGIBLE", restore=True)

        transition_key = str(uuid.uuid4())
        transition_headers = {
            **write_headers, "idempotency-key": transition_key,
            "if-match": '"v6"',
        }
        first = client.post(
            transition_path, headers=transition_headers,
            json=transition_body,
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"]["from_stage"] == "SURVEY"
        assert first.json()["data"]["to_stage"] == "REQUIREMENT"
        assert first.headers["etag"] == '"v7"'
        replay = client.post(
            transition_path, headers=transition_headers,
            json=transition_body,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == first.json()["data"]

    with review_fixture.schema.connect(database) as db:
        assert db.execute(
            "SELECT current_stage_key,lock_version FROM "
            "plm.wfl_project_workflows WHERE workflow_id=%s",
            (workflow_id,),
        ).fetchone() == ("REQUIREMENT", 7)
        assert db.execute(
            "SELECT item_key,item_state FROM plm.wfl_checklist_items "
            "WHERE workflow_id=%s AND item_key IN "
            "('SURVEY_ACTUAL_SOURCES','SURVEY_CONCLUSION') "
            "ORDER BY item_key", (workflow_id,),
        ).fetchall() == [
            ("SURVEY_ACTUAL_SOURCES", "PASS"),
            ("SURVEY_CONCLUSION", "PASS"),
        ]
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_checklist_records "
            "WHERE project_id=%s AND result='PASS'", (project,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_stage_transitions "
            "WHERE project_id=%s AND from_stage='SURVEY' "
            "AND to_stage='REQUIREMENT'", (project,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_transition_gate_items "
            "WHERE project_id=%s", (project,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND action='WORKFLOW_CHECKLIST_RECORDED'", (project,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND action='WORKFLOW_STAGE_TRANSITIONED'", (project,),
        ).fetchone()[0] == 1


def main() -> None:
    review_fixture.main(verify_workflow)
    print(
        "SUR_06_A05_WORKFLOW_PG_PASS: Windows 11/PostgreSQL 18.6 real "
        "Survey qualification preview, owner locks, write-time drift reproof, "
        "concurrent version fence, two PASS records, SURVEY->REQUIREMENT, "
        "Audit/receipt/replay and isolated cleanup verified"
    )


if __name__ == "__main__":
    main()
