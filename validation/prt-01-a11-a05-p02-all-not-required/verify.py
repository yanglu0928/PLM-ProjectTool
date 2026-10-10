"""Real PG/HTTP Prototype all-NOT_REQUIRED qualification and transition."""

from __future__ import annotations

import runpy
import shutil
import socket
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.prototype.application.create_identity import (
    CreatePrototypeIdentity, PrototypeIdentityCreateService,
)
from plm_assistant.modules.prototype.application.mark_not_required import (
    MarkPrototypeNotRequired, PrototypeScopeDecisionService,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.scope_decision_repository import (
    SqlAlchemyPrototypeScopeDecisionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
physical = runpy.run_path(str(
    ROOT / "validation/prt-01-a11-a05-p01-physical-pg/verify.py"
))
_run = physical["_run"]
PG_SOURCE, VECTOR_SOURCE = physical["PG_SOURCE"], physical["VECTOR_SOURCE"]
ORIGIN = "http://localhost"
PORT = 55434  # Existing Requirement verifier binds this explicit test port.
ITEMS = ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE")


class UnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"all-NOT_REQUIRED fixture used {name}")


def _after_prototype(*, scratch: Path, runtime, database, ids, pm, pm_token,
                     reviewer, reviewer_token,
                     requirement, requirement_version, requirement_review_round,
                     workflow_id, guard,
                     audit, sessions, origins, csrf, project_evidence,
                     additional_requirement) -> None:
    storage_root = scratch / "private-documents"
    storage_root.mkdir()
    storage = LocalFileStorage(storage_root)
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ), receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        clock=lambda: datetime.now(timezone.utc),
    )
    creator = PrototypeIdentityCreateService(
        **common, repository=SqlAlchemyPrototypeIdentityCreateRepository(),
    )
    prototype = creator.create_prototype(CreatePrototypeIdentity(
        pm_token, csrf, uuid.uuid4(), ids["project"],
        "Synthetic no-prototype decision", str(uuid.uuid4()),
    ))
    unused = UnusedDependency()

    def routers(*, enabled: bool):
        optional = {"artifact_storage": storage} if enabled else {}
        return create_app(
            workflow_checklist_qualification_router=(
                create_windows_workflow_checklist_qualification_router(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, documents=unused,
                    downloads=unused, parse_results=unused, **optional,
                )
            ),
            workflow_checklist_record_router=(
                create_windows_workflow_checklist_record_router(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=unused,
                    downloads=unused, parse_results=unused, **optional,
                )
            ),
            workflow_transition_router=(
                create_windows_workflow_stage_transition_router(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=unused,
                    downloads=unused, parse_results=unused, **optional,
                )
            ),
        )

    prefix = f"/api/v1/projects/{ids['project']}/workflow"
    get_headers = {"cookie": "plm_session=" + pm_token.hex(), "host": "localhost"}
    write_headers = {
        **get_headers, "x-csrf-token": csrf.hex(), "origin": ORIGIN,
    }
    body = {"result": "PASS", "reason": "Synthetic complete scope",
            "impact": "Validation only", "evidence_refs": [str(project_evidence)],
            "exception_refs": []}
    with TestClient(routers(enabled=False), base_url=ORIGIN) as closed:
        assert closed.get(
            f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
            headers=get_headers,
        ).status_code == 422
        assert closed.post(
            f"{prefix}/checklist-items/{ITEMS[0]}:record", json=body,
            headers={**write_headers, "if-match": '"v10"',
                     "idempotency-key": str(uuid.uuid4())},
        ).status_code == 422
        assert closed.post(
            f"{prefix}:transition", json={"target_stage_key": "SOLUTION",
                                      "reason": "Not enabled", "gate_snapshot_refs": []},
            headers={**write_headers, "if-match": '"v10"',
                     "idempotency-key": str(uuid.uuid4())},
        ).status_code == 422

    with TestClient(routers(enabled=True), base_url=ORIGIN) as client:
        no_decision = client.get(
            f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
            headers=get_headers,
        )
        assert no_decision.status_code == 409, no_decision.text
        assert no_decision.json()["error"]["code"] == "WORKFLOW_GATE_NOT_SATISFIED"

        decision = PrototypeScopeDecisionService(
            **common, repository=SqlAlchemyPrototypeScopeDecisionRepository(),
        ).mark_not_required(MarkPrototypeNotRequired(
            pm_token, csrf, uuid.uuid4(), ids["project"],
            prototype.prototype_id, 0, (requirement_version,),
            "No interactive prototype required for synthetic requirement",
            "Use the existing standard configuration", None, None,
            str(uuid.uuid4()),
        ))
        assert decision.prototype_state == "NOT_REQUIRED"
        assert decision.confirmed_by == pm  # PM action, not customer sign-off.

        preview = client.get(
            f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
            headers=get_headers,
        )
        assert preview.status_code == 200, preview.text
        first_data = preview.json()["data"]
        assert first_data["stage_key"] == "PROTOTYPE"
        assert first_data["qualified_subjects"] == [{
            "subject_type": "REQ-03", "subject_id": str(requirement.requirement_id),
            "subject_version_id": str(requirement_version),
            "review_round_ref": str(requirement_review_round),
        }]
        assert first_data["evidence_refs"] == [str(project_evidence)]
        assert "requirement_version_refs" not in first_data

        etag = '"v10"'
        for item in ITEMS:
            qualified = client.get(
                f"{prefix}/checklist-items/{item}/qualification",
                headers=get_headers,
            )
            assert qualified.status_code == 200, qualified.text
            assert qualified.headers["etag"] == etag
            evidence = qualified.json()["data"]["evidence_refs"]
            written = client.post(
                f"{prefix}/checklist-items/{item}:record",
                json={**body, "evidence_refs": evidence},
                headers={**write_headers, "if-match": etag,
                         "idempotency-key": str(uuid.uuid4())},
            )
            assert written.status_code == 200, written.text
            etag = written.headers["etag"]
        assert etag == '"v12"'

        key = str(uuid.uuid4())
        request = {"target_stage_key": "SOLUTION",
                   "reason": "Synthetic complete scope accepted",
                   "gate_snapshot_refs": []}
        headers = {**write_headers, "if-match": etag, "idempotency-key": key}
        first = client.post(f"{prefix}:transition", json=request, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["data"]["from_stage"] == "PROTOTYPE"
        assert first.json()["data"]["to_stage"] == "SOLUTION"
        assert first.headers["etag"] == '"v13"'
        replay = client.post(f"{prefix}:transition", json=request, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == first.json()["data"]

    with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                         dbname=database, autocommit=True) as db:
        assert db.execute(
            "SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows "
            "WHERE workflow_id=%s", (workflow_id,),
        ).fetchone() == ("SOLUTION", 13)
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_checklist_records "
            "WHERE project_id=%s AND stage_key='PROTOTYPE' AND result='PASS'",
            (ids["project"],),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.wfl_stage_transitions "
            "WHERE project_id=%s AND from_stage='PROTOTYPE' AND to_stage='SOLUTION'",
            (ids["project"],),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND action='PROTOTYPE_MARKED_NOT_REQUIRED' AND outcome='SUCCESS'",
            (ids["project"],),
        ).fetchone()[0] == 1


def main() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError("port 55434 is occupied; existing PostgreSQL untouched")
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    scratch = Path(tempfile.mkdtemp(prefix="plm-prt-a05-p02-", dir=temp_root)).resolve()
    if not scratch.is_relative_to(temp_root) or not str(scratch).isascii():
        raise RuntimeError("isolated ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    try:
        for name in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / name, install / name)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(path, install / "share/extension" / path.name)
        binaries = install / "bin"
        data = scratch / "data"
        log = scratch / "postgres.log"
        _run([str(binaries / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
              "-A", "trust", "--no-locale", "-E", "UTF8"])
        _run([str(binaries / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
              "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start"], detached=True)
        req = runpy.run_path(str(
            ROOT / "validation/req-01-a12-a05-workflow-pg/verify.py"
        ))
        req["main"](after_prototype=lambda **context: _after_prototype(
            scratch=scratch, **context,
        ))
        print(
            "PRT_01_A11_A05_P02_ALL_NOT_REQUIRED_HTTP_PG_PASS: real "
            "Requirement->Prototype->Solution, missing decision rejected, "
            "two current qualifications/PASS, Audit, replay and cleanup"
        )
    finally:
        control = install / "bin/pg_ctl.exe"
        data = scratch / "data"
        if control.is_file() and data.is_dir():
            status = subprocess.run(
                [str(control), "-D", str(data), "status"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
            if status.returncode == 0:
                _run([str(control), "-D", str(data), "-m", "fast", "-w", "stop"])
                status = subprocess.run(
                    [str(control), "-D", str(data), "status"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30, check=False,
                )
            if status.returncode == 0:
                raise RuntimeError("isolated PostgreSQL still running; temp data preserved")
        if (scratch.is_relative_to(temp_root) and scratch != temp_root
                and scratch.name.startswith("plm-prt-a05-p02-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
