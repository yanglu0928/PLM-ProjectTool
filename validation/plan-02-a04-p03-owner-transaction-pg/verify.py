"""Disposable real PostgreSQL proof for the PlanVersion transaction owner.

This reuses the existing synthetic Approved Solution fixture. It creates no
customer data, starts no persistent service, and only writes to a disposable PG.
"""

from __future__ import annotations

import importlib.util
import hashlib
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

from plm_assistant.entrypoints.windows_plan_version import (
    create_windows_plan_version_create_service,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.plan.application.create_plan import (
    CreatePlan, PlanCreateService,
)
from plm_assistant.modules.plan.application.create_plan_version import (
    CreatePlanVersion, PlanVersionCreateError, PlanVersionCreateService,
)
from plm_assistant.modules.plan.infrastructure.create_repository import (
    SqlAlchemyPlanCreateRepository,
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
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery,
)


ROOT = Path(__file__).resolve().parents[2]
FULL_SOURCE_SPEC = importlib.util.spec_from_file_location(
    "plan_owner_full_approved_solution_fixture",
    ROOT / "validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py",
)
assert FULL_SOURCE_SPEC and FULL_SOURCE_SPEC.loader
full = importlib.util.module_from_spec(FULL_SOURCE_SPEC)
FULL_SOURCE_SPEC.loader.exec_module(full)


def _main_fixture():
    fixture = full.terminal.prior.prior.fixture
    runner = fixture.prior.prior.prior.prior.prior.prior.prior.prior
    return runner


def _connection(port: int) -> dict[str, object]:
    return {"host": "127.0.0.1", "port": port,
            "user": "poc_admin", "dbname": "postgres"}


def _restore_coverage_edge(context: dict[str, object]) -> None:
    """Restore a real synthetic Requirement->approved Section trace after the
    upstream fixture's intentional trace-revocation negative case."""
    project, port = context["project"], context["port"]
    with psycopg.connect(**_connection(port)) as db:
        section, section_version, requirement, requirement_version = db.execute(
            "SELECT s.solution_section_id,v.solution_section_version_id,"
            "r.requirement_id,r.requirement_version_id "
            "FROM plm.sol_sections s JOIN plm.sol_section_versions v "
            "ON v.solution_section_id=s.solution_section_id AND v.project_id=s.project_id "
            "JOIN plm.sol_section_requirement_refs r "
            "ON r.solution_section_version_id=v.solution_section_version_id "
            "WHERE s.project_id=%s AND s.current_approved_version_ref="
            "v.solution_section_version_id ORDER BY v.version_no DESC LIMIT 1",
            (project,),
        ).fetchone()
    creator, _ = full.terminal.prior._trace_services(
        runtime=context["runtime"], license_guard=context["license_guard"],
        audit=context["audit"],
    )
    trace_module = full.terminal.prior
    creator.create_refs(trace_module.CreateTraceLinkRefs(
        context["token"], context["csrf"], uuid.uuid4(), project,
        trace_module.TraceResourceVersionRef(
            "REQ-03", requirement, requirement_version),
        trace_module.TraceResourceVersionRef(
            "SOL-05", section, section_version),
        "IMPLEMENTS",
    ), idempotency_key="plan-owner-pg-coverage-restore-0001")


def _solution_proof(service, context: dict[str, object]):
    project, port = context["project"], context["port"]
    with psycopg.connect(**_connection(port)) as db:
        outline, version = db.execute(
            "SELECT solution_outline_id,current_approved_version_ref "
            "FROM plm.sol_outlines WHERE project_id=%s AND "
            "current_approved_version_ref IS NOT NULL LIMIT 1", (project,),
        ).fetchone()
    if outline is None or version is None:
        raise AssertionError("synthetic fixture has no current Approved Outline")
    command = OutlineCurrentFactQuery(
        context["token"], uuid.uuid4(), project, outline, version)
    with context["runtime"].unit_of_work() as transaction:
        proof = service._solution_proof.prove(transaction, command=command)
    return command, proof


def _approve_current_outline(context: dict[str, object], storage_root: Path) -> None:
    from fastapi.testclient import TestClient
    from plm_assistant.entrypoints.api import create_app
    from plm_assistant.entrypoints.windows_project_review import (
        create_windows_project_review_router,
    )
    from plm_assistant.entrypoints.windows_solution_outline import (
        create_windows_outline_review_subject,
        create_windows_outline_review_submission_router,
    )
    from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
    from plm_assistant.modules.auth.application.session_service import SessionService
    from plm_assistant.modules.auth.infrastructure.session_repository import (
        SqlAlchemySessionRepository,
    )

    project, port = context["project"], context["port"]
    with psycopg.connect(**_connection(port)) as db:
        outline, version = db.execute(
            "SELECT solution_outline_id,solution_outline_version_id "
            "FROM plm.sol_outline_versions WHERE project_id=%s "
            "ORDER BY version_no DESC LIMIT 1", (project,),
        ).fetchone()
        reviewer = db.execute(
            "SELECT m.user_id,u.credential_version FROM plm.prj_project_members m "
            "JOIN plm.auth_users u ON u.user_id=m.user_id "
            "WHERE m.project_id=%s AND m.project_role='CUSTOMER_MEMBER' "
            "AND m.state='ACTIVE' ORDER BY m.effective_at LIMIT 1", (project,),
        ).fetchone()
    if reviewer is None:
        raise AssertionError("synthetic approved Outline fixture has no Reviewer")
    reviewer_id, credential_version = reviewer
    reviewer_token, reviewer_csrf = uuid.uuid4().bytes + uuid.uuid4().bytes, uuid.uuid4().bytes + uuid.uuid4().bytes
    with psycopg.connect(**_connection(port)) as db, db.transaction():
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) VALUES "
            "(%s,%s,%s,%s,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours')",
            (hashlib.sha256(reviewer_token).digest(),
             hashlib.sha256(reviewer_csrf).digest(), reviewer_id, credential_version),
        )

    runtime, guard, audit = (context[key] for key in (
        "runtime", "license_guard", "audit"))
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    documents, downloads, parse_results = (context[key] for key in (
        "documents", "downloads", "parse_results"))
    submit = create_windows_outline_review_submission_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit,
        document_storage_root=storage_root,
        parse_result_storage_root=storage_root,
        documents=documents, downloads=downloads, parse_results=parse_results,
    )
    submit_path = (f"/api/v1/projects/{project}/solution-outlines/{outline}/"
                   f"versions/{version}:submit-review")
    submit_headers = full._headers(
        context["token"], context["csrf"], "plan-owner-outline-submit-0001")
    body = {
        "reviewer_ids": [str(reviewer_id)],
        "policy_ref": "SOLUTION_OUTLINE_ALL_V1",
        "due_at": None, "submission_note": None,
    }
    with TestClient(create_app(solution_outline_review_submission_router=submit),
                    base_url="https://plm.example.test") as app:
        response = app.post(submit_path, headers=submit_headers, json=body)
        assert response.status_code == 201, response.text
        review_id = uuid.UUID(response.json()["data"]["review_id"])
        round_id = uuid.UUID(response.json()["data"]["review_round_id"])

    outline_subject = create_windows_outline_review_subject(
        runtime=runtime, license_guard=guard, audit=audit,
        document_storage_root=storage_root,
        parse_result_storage_root=storage_root,
        documents=documents, downloads=downloads, parse_results=parse_results,
        terminal_context=True,
    )
    review_router = create_windows_project_review_router(
        runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit,
        documents=documents, downloads=downloads, parse_results=parse_results,
        outline_subject=outline_subject,
    )
    decide_path = (f"/api/v1/projects/{project}/reviews/{review_id}/rounds/"
                   f"{round_id}:decide")
    decision_headers = full._headers(
        reviewer_token, reviewer_csrf, "plan-owner-outline-approve-0001")
    with TestClient(create_app(review_command_router=review_router),
                    base_url="https://plm.example.test") as app:
        response = app.post(decide_path, headers=decision_headers,
                            json={"decision": "APPROVE", "comment": None})
        assert response.status_code == 200, response.text
    with psycopg.connect(**_connection(port)) as db:
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_outlines "
            "WHERE solution_outline_id=%s", (outline,),
        ).fetchone()[0] == version


def _solution_ref(ref) -> dict[str, object]:
    return {
        "resource_kind": ref.resource_kind,
        "resource_id": str(ref.resource_id),
        "version_id": str(ref.version_id),
        "spec_series_id": str(ref.spec_series_id) if ref.spec_series_id else None,
        "spec_type": ref.spec_type,
    }


def _draft(proof, *, risk: str = "Synthetic acceptance risk") -> dict[str, object]:
    outline_ref = {
        "resource_kind": "OUTLINE", "resource_id": str(proof.outline_id),
        "version_id": str(proof.outline_version_id),
        "spec_series_id": None, "spec_type": None,
    }
    solution_refs = [outline_ref]
    for section in proof.sections:
        solution_refs.append({
            "resource_kind": "SECTION", "resource_id": str(section.section_id),
            "version_id": str(section.section_version_id),
            "spec_series_id": None, "spec_type": None,
        })
        for qualified in section.qualified_specs:
            solution_refs.append(_solution_ref(qualified.ref))
    requirement_refs = [{
        "requirement_id": str(ref.requirement_id),
        "requirement_version_id": str(ref.requirement_version_id),
    } for ref in proof.requirement_refs]
    root_id, child_id = uuid.uuid4(), uuid.uuid4()

    def item(*, item_id, code, name, parent, level, roles, conditions, acceptance):
        return {
            "wbs_item_id": str(item_id), "parent_item_id": str(parent) if parent else None,
            "wbs_code": code, "name": name, "level": level,
            "category": "IMPLEMENTATION", "owner_ref": None,
            "support_role_refs": roles,
            "planned_start": "2026-10-26", "planned_finish": "2026-10-27",
            "duration_minutes": 480, "actual_start": None, "actual_finish": None,
            "item_state": "NOT_STARTED", "entry_conditions": conditions,
            "acceptance_criteria": acceptance,
            "requirement_refs": requirement_refs,
            "solution_refs": solution_refs, "prototype_refs": [],
            "evidence_refs": [], "output_refs": [], "risk": risk,
            "explicit_exclusion": None,
        }

    return {
        "approved_solution_refs": solution_refs,
        "wbs_items": [
            item(item_id=root_id, code="1", name="Approved solution delivery",
                 parent=None, level=1, roles=["PROJECT_MANAGER"],
                 conditions=["Scope approved"], acceptance=["Delivery accepted"]),
            item(item_id=child_id, code="1.1", name="Implement validated scope",
                 parent=root_id, level=2, roles=["IMPLEMENTATION_MEMBER"],
                 conditions=["Inputs fixed"], acceptance=["Tests pass"]),
        ],
        "dependencies": [{
            "dependency_id": str(uuid.uuid4()),
            "predecessor_item_id": str(root_id),
            "successor_item_id": str(child_id),
            "dependency_type": "FS", "lag": 0, "lag_unit": None,
            "lag_reason": None,
        }],
        "milestones": [{
            "name": "Synthetic milestone", "target_date": "2026-10-27",
            "duration_days": 1, "acceptance_rule": "Tests pass",
            "gate_ref": None, "wbs_item_refs": [str(root_id), str(child_id)],
        }],
        "calendar_ref": "CN_WORKDAY", "exclusions": [],
    }


def _snapshot_counts(port: int, plan_id: uuid.UUID) -> tuple[int, ...]:
    tables = (
        "pln_plan_versions", "pln_wbs_items", "pln_wbs_support_roles",
        "pln_wbs_conditions", "pln_wbs_dependencies", "pln_milestones",
        "pln_milestone_item_refs", "pln_item_solution_refs",
        "pln_item_requirement_refs",
    )
    with psycopg.connect(**_connection(port)) as db:
        return tuple(db.execute(
            f"SELECT count(*) FROM plm.{table} WHERE plan_id=%s", (plan_id,),
        ).fetchone()[0] for table in tables)


class _FailingAudit:
    def append(self, transaction, event) -> None:
        raise RuntimeError("synthetic audit failure")


def verify_owner(context: dict[str, object]) -> None:
    _restore_coverage_edge(context)
    runtime, project = context["runtime"], context["project"]
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    plan_creator = PlanCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=context["license_guard"], authorization=authorization,
        repository=SqlAlchemyPlanCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=context["audit"],
    )
    plan = plan_creator.create(CreatePlan(
        context["token"], context["csrf"], uuid.uuid4(), project,
        "Synthetic Plan Owner Transaction Test", "plan-owner-root-create-0001",
    ))
    with tempfile.TemporaryDirectory(prefix="plan-owner-docs-") as root:
        _approve_current_outline(context, Path(root))
        service = create_windows_plan_version_create_service(
            runtime=runtime, license_guard=context["license_guard"],
            audit=context["audit"], document_storage_root=Path(root),
            parse_result_storage_root=Path(root), documents=context["documents"],
            downloads=context["downloads"], parse_results=context["parse_results"],
        )
        _, proof = _solution_proof(service, context)
        draft = _draft(proof)
        command = CreatePlanVersion(
            context["token"], context["csrf"], uuid.uuid4(), project, plan.plan_id,
            draft, "plan-version-create-pg-0001",
        )
        first = service.create(command)
        replay = service.create(command)
        assert first.plan_version_id == replay.plan_version_id
        assert first.version_no == replay.version_no == 1
        counts = _snapshot_counts(context["port"], plan.plan_id)
        assert counts == (1, 2, 2, 4, 1, 1, 2, len(draft["approved_solution_refs"]) * 2,
                          len(proof.requirement_refs) * 2), counts

        conflict_draft = _draft(proof, risk="Changed payload under same idempotency key")
        conflict = CreatePlanVersion(
            context["token"], context["csrf"], uuid.uuid4(), project, plan.plan_id,
            conflict_draft, command.idempotency_key,
        )
        try:
            service.create(conflict)
        except PlanVersionCreateError as error:
            assert error.code == "CONFLICT_IDEMPOTENCY", error.code
        else:
            raise AssertionError("same-key payload conflict was accepted")
        assert _snapshot_counts(context["port"], plan.plan_id) == counts

        bad_draft = _draft(proof)
        bad_version = str(uuid.uuid4())
        bad_draft["approved_solution_refs"][0]["version_id"] = bad_version
        for item in bad_draft["wbs_items"]:
            item["solution_refs"][0]["version_id"] = bad_version
        rejected = CreatePlanVersion(
            context["token"], context["csrf"], uuid.uuid4(), project, plan.plan_id,
            bad_draft, "plan-version-create-unapproved-source-0001",
        )
        try:
            service.create(rejected)
        except PlanVersionCreateError as error:
            assert error.code == "PLAN_SOURCE_UNAVAILABLE", error.code
        else:
            raise AssertionError("unapproved Outline version was accepted")
        assert _snapshot_counts(context["port"], plan.plan_id) == counts

        rollback_command = CreatePlanVersion(
            context["token"], context["csrf"], uuid.uuid4(), project, plan.plan_id,
            _draft(proof, risk="Synthetic audit rollback"),
            "plan-version-audit-failure-0001",
        )
        failing_audit_service = create_windows_plan_version_create_service(
            runtime=runtime, license_guard=context["license_guard"],
            audit=_FailingAudit(), document_storage_root=Path(root),
            parse_result_storage_root=Path(root), documents=context["documents"],
            downloads=context["downloads"], parse_results=context["parse_results"],
        )
        try:
            failing_audit_service.create(rollback_command)
        except PlanVersionCreateError:
            pass
        else:
            raise AssertionError("synthetic Audit failure did not abort PlanVersion")
        assert _snapshot_counts(context["port"], plan.plan_id) == counts
        recovered = service.create(rollback_command)
        assert recovered.version_no == 2
        after_recovery = _snapshot_counts(context["port"], plan.plan_id)
        assert after_recovery == tuple(
            prior + increment for prior, increment in zip(
                counts, (1, 2, 2, 4, 1, 1, 2,
                         len(draft["approved_solution_refs"]) * 2,
                         len(proof.requirement_refs) * 2), strict=True)
        ), after_recovery

        parallel = [CreatePlanVersion(
            context["token"], context["csrf"], uuid.uuid4(), project, plan.plan_id,
            _draft(proof, risk=f"Concurrent snapshot {index}"),
            f"plan-version-parallel-create-{index:04d}",
        ) for index in (1, 2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results = list(pool.map(service.create, parallel))
        assert sorted(item.version_no for item in concurrent_results) == [3, 4]

    print("PLAN_VERSION_OWNER_POSTGRESQL_PASS: complete snapshot, current approved "
          "source proof, same-key replay/conflict, invalid source rejection, "
          "Audit rollback/retry and concurrent version numbering")


def _with_plan_owner(case: str, **context) -> None:
    assert case == "APPROVE"
    full.original_terminal(case, **context)
    full._outline_full(**context)
    verify_owner(context)


def main(pg_root: Path, vector_source: Path) -> None:
    runner = _main_fixture()
    runner.helper.PG_SOURCE = pg_root
    runner.helper.VECTOR_SOURCE = vector_source
    full.terminal._terminal = _with_plan_owner
    full.terminal._run("APPROVE")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-root", type=Path, required=True)
    parser.add_argument("--vector-source", type=Path, required=True)
    arguments = parser.parse_args()
    main(arguments.pg_root, arguments.vector_source)
