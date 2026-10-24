"""Disposable PG proof for current Approved RequirementVersion outline use."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineRequirementUseError,
    OutlineRequirementUseProofService,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "requirement_use_project_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def denied(action):
    try:
        action()
    except OutlineRequirementUseError:
        return
    raise AssertionError("noncurrent RequirementVersion accepted")


def update(port, command, params):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(command, params)


def on_created(*, runtime, project, other_project, manager, port, **_unused):
    requirement = uuid.uuid4()
    version = uuid.uuid4()
    review = uuid.uuid4()
    round_id = uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,"
            "requirement_code,requirement_code_normalized,requirement_state,"
            "current_approved_version_ref,created_by) "
            "VALUES (%s,%s,'R-OUTLINE','R-OUTLINE','ACTIVE',%s,%s)",
            (requirement, project, version, manager))
        db.execute(
            "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
            "requirement_id,project_id,version_no,version_state,statement,"
            "rationale,domain_name,priority,risk,requirement_classification,"
            "content_fingerprint,declared_source_count,declared_acceptance_count,"
            "declared_capability_count,declared_assumption_count,"
            "declared_exclusion_count,declared_dependency_count,"
            "declared_ai_task_count,review_ref,review_round_ref,created_by) "
            "VALUES (%s,%s,%s,1,'APPROVED','Synthetic requirement',"
            "'Synthetic rationale','Domain','HIGH','LOW','STANDARD_FUNCTION',"
            "%s,1,0,0,0,0,0,0,%s,%s,%s)",
            (version, requirement, project, b"r" * 32, review, round_id, manager))
    proof = OutlineRequirementUseProofService(
        approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof())
    with runtime.unit_of_work() as tx:
        result = proof.prove(
            tx, project_id=project, requirement_id=requirement,
            requirement_version_id=version)
        assert result.content_fingerprint == b"r" * 32
        assert result.review_id == review and result.review_round_id == round_id
        denied(lambda: proof.prove(
            tx, project_id=other_project, requirement_id=requirement,
            requirement_version_id=version))
        denied(lambda: proof.prove(
            tx, project_id=project, requirement_id=requirement,
            requirement_version_id=uuid.uuid4()))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            try:
                db.execute(
                    "SELECT requirement_id FROM plm.req_requirements "
                    "WHERE requirement_id=%s FOR UPDATE NOWAIT",
                    (requirement,))
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("Requirement proof did not retain root lock")
    update(port, "UPDATE plm.req_requirements SET "
           "current_approved_version_ref=NULL WHERE requirement_id=%s",
           (requirement,))
    with runtime.unit_of_work() as tx:
        denied(lambda: proof.prove(
            tx, project_id=project, requirement_id=requirement,
            requirement_version_id=version))
    update(port, "UPDATE plm.req_requirements SET "
           "current_approved_version_ref=%s,requirement_state='ARCHIVED' "
           "WHERE requirement_id=%s", (version, requirement))
    with runtime.unit_of_work() as tx:
        denied(lambda: proof.prove(
            tx, project_id=project, requirement_id=requirement,
            requirement_version_id=version))
    return 0


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    print("SOL_03_A04_P03_P02_A02_REQUIREMENT_USE_PROOF_PASS: current Approved "
          "RequirementVersion, cross-project, old pointer, archive and root lock")
