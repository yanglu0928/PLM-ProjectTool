"""Win11 disposable PG proof: fixed Requirement/PROJECT/GLOBAL refs through Owner."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_outline_version import (
    CreateOutlineVersion, OutlineVersionCreateError, OutlineVersionCreateService,
)
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.create_section import CreateSection, SectionCreateService
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef, OutlineRequirementRef, OutlineVersionDraftInput,
)
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseProofService
from plm_assistant.modules.solution.application.prove_outline_version_input import OutlineVersionInputProofService
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.solution.application.set_reference_eligibility import SetReferenceEligibility
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_version_base import SqlAlchemyCurrentOutlineVersionBase
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import SqlAlchemyOutlineVersionCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import (
    SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository,
)
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = module(
    "dual_scope_owner_project_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
composition = module(
    "dual_scope_owner_reference_composition",
    "validation/sol-03-a04-p02-p03-reference-use-composition/verify.py")


def rejects(code: str, action) -> None:
    try:
        action()
    except OutlineVersionCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected OutlineVersion rejection: " + code)


def common(*, runtime, license_guard, audit):
    return dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )


def inputs(references):
    return OutlineVersionInputProofService(
        bases=SqlAlchemyCurrentOutlineVersionBase(),
        sections=OutlineSectionUseProofService(
            sections=SqlAlchemySectionReadRepository()),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        references=references,
    )


def create_outline_section(*, runtime, license_guard, audit, token, csrf,
                           project, suffix):
    ports = common(runtime=runtime, license_guard=license_guard, audit=audit)
    outline = OutlineCreateService(
        **ports, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          f"{suffix} outline", f"outline-owner-{suffix}-root-0001"))
    section = SectionCreateService(
        **ports, repository=SqlAlchemySectionCreateRepository()).create(
            CreateSection(token, csrf, uuid.uuid4(), project,
                          outline.solution_outline_id, "Overview",
                          f"outline-owner-{suffix}-section-0001"))
    return outline.solution_outline_id, section.solution_section_id


def seed_approved_requirement(*, port, project, actor, code):
    requirement, version = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        # Requirement Review is a separate Owner; this fixture only supplies
        # its immutable approved-version proof to the Solution consumer.
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,"
            "requirement_code,requirement_code_normalized,requirement_state,"
            "current_approved_version_ref,created_by) "
            "VALUES (%s,%s,%s,%s,'ACTIVE',%s,%s)",
            (requirement, project, code, code, version, actor))
        db.execute(
            "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
            "requirement_id,project_id,version_no,version_state,statement,"
            "rationale,domain_name,priority,risk,requirement_classification,"
            "content_fingerprint,declared_source_count,declared_acceptance_count,"
            "declared_capability_count,declared_assumption_count,"
            "declared_exclusion_count,declared_dependency_count,"
            "declared_ai_task_count,review_ref,review_round_ref,created_by) "
            "VALUES (%s,%s,%s,1,'APPROVED','Synthetic approved input',"
            "'Synthetic rationale','Domain','HIGH','LOW','STANDARD_FUNCTION',"
            "%s,1,0,0,0,0,0,0,%s,%s,%s)",
            (version, requirement, project, b"r" * 32,
             uuid.uuid4(), uuid.uuid4(), actor))
    return requirement, version


def assert_rows(*, port, outline, version, project, requirement, requirement_version,
                reference, reference_version, scope, actor):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        row = db.execute(
            "SELECT version_no,version_state,declared_section_count,"
            "declared_requirement_count,declared_reference_count,created_by "
            "FROM plm.sol_outline_versions WHERE solution_outline_version_id=%s",
            (version,)).fetchone()
        assert row == (1, "DRAFT", 1, 1, 1, actor), row
        req = db.execute(
            "SELECT requirement_id,requirement_version_id,ordinal "
            "FROM plm.sol_outline_requirement_refs "
            "WHERE solution_outline_version_id=%s", (version,)).fetchone()
        assert req == (requirement, requirement_version, 1), req
        ref = db.execute(
            "SELECT reference_solution_id,reference_version_id,reference_scope,"
            "source_project_id,ordinal FROM plm.sol_outline_reference_refs "
            "WHERE solution_outline_version_id=%s", (version,)).fetchone()
        assert ref == (reference, reference_version, scope,
                       project if scope == "PROJECT" else None, 1), ref
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_sections "
            "WHERE solution_outline_version_id=%s AND ordinal=1",
            (version,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_version_create_results "
            "WHERE solution_outline_version_id=%s AND project_id=%s",
            (version, project)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_OUTLINE_VERSION_CREATED' AND target_version_id=%s",
            (version,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_OUTLINE_VERSION_CREATE' AND result_ref_id=%s",
            (version,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_versions "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_version_create_results "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_requirement_refs "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.sol_outline_reference_refs "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_OUTLINE_VERSION_CREATED' AND target_object_id=%s",
            (outline,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_OUTLINE_VERSION_CREATE'").fetchone()[0] == 1


def project_created(*, runtime, sources, audit, license_guard,
                    created, project, other_project, manager, token, csrf,
                    downloads, parse_results, scratch, locator, content, port,
                    **_unused):
    references, eligibility, _ = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 0, "ELIGIBLE", "Outline source reviewed",
        "dual-scope-owner-project-eligible-0001"))
    outline, section = create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="project")
    requirement, requirement_version = seed_approved_requirement(
        port=port, project=project, actor=manager, code="R-DUAL-OWNER-P")
    owner = OutlineVersionCreateService(
        **common(runtime=runtime, license_guard=license_guard, audit=audit),
        inputs=inputs(references),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, requirement_version),),
        (OutlineReferenceRef("PROJECT", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    command = CreateOutlineVersion(
        token, csrf, uuid.uuid4(), draft, "dual-scope-owner-project-0001")
    first = owner.create(command)
    assert owner.create(replace(command, trace_id=uuid.uuid4())) == first
    assert_rows(
        port=port, outline=outline, version=first.solution_outline_version_id,
        project=project, requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id,
        scope="PROJECT", actor=manager)
    rejects("RESOURCE_NOT_FOUND", lambda: owner.create(replace(
        command, draft=replace(draft, project_id=other_project),
        idempotency_key="dual-scope-owner-project-cross-0001")))
    file = scratch / "private-documents" / locator
    original = file.read_bytes()
    try:
        file.write_bytes(b"X" * len(content))
        rejects("SOURCE_UNAVAILABLE", lambda: owner.create(replace(
            command, idempotency_key="dual-scope-owner-project-tamper-0001")))
    finally:
        file.write_bytes(original)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 1, "RESTRICTED", "Current use revoked",
        "dual-scope-owner-project-restrict-0001"))
    rejects("SOURCE_UNAVAILABLE", lambda: owner.create(replace(
        command, idempotency_key="dual-scope-owner-project-restrict-0001")))
    assert_rows(
        port=port, outline=outline, version=first.solution_outline_version_id,
        project=project, requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id,
        scope="PROJECT", actor=manager)
    return 0


def global_qualified(*, runtime, request, sources, audit, license_guard,
                     downloads, parse_results, confirmed, qualified, port,
                     **_unused):
    references, eligibility, source_common = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    created = ReferenceCreateService(
        **source_common,
        repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(
                request, composition.global_fixture.CSRF,
                "Global dual-scope source", "dual-scope-owner-global-ref-0001"))
    eligibility.set(SetReferenceEligibility(
        composition.global_fixture.TOKEN, composition.global_fixture.CSRF,
        uuid.uuid4(), "GLOBAL", None, created.reference_solution_id,
        0, "ELIGIBLE", "Global source reviewed",
        "dual-scope-owner-global-eligible-0001"))
    token, csrf = b"y" * 32, b"z" * 32
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        manager = fixture.user(db, "Outline Global Project Manager", token, csrf)
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('SOLDUALGLOBAL','soldualglobal',"
            "'Global target project',%s) RETURNING project_id",
            (manager,)).fetchone()[0]
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'SOL','sol','Solution') "
            "RETURNING department_id", (project,)).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,"
            "department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
            (project, manager, department))
    outline, section = create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="global")
    requirement, requirement_version = seed_approved_requirement(
        port=port, project=project, actor=manager, code="R-DUAL-OWNER-G")
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, requirement_version),),
        (OutlineReferenceRef("GLOBAL", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    owner_ports = common(runtime=runtime, license_guard=license_guard, audit=audit)
    owner = OutlineVersionCreateService(
        **owner_ports, inputs=inputs(references),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    command = CreateOutlineVersion(
        token, csrf, uuid.uuid4(), draft, "dual-scope-owner-global-0001")
    first = owner.create(command)
    assert owner.create(replace(command, trace_id=uuid.uuid4())) == first
    assert_rows(
        port=port, outline=outline, version=first.solution_outline_version_id,
        project=project, requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id,
        scope="GLOBAL", actor=manager)
    expired_reference = ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=references._sources,
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository(),
        clock=lambda: confirmed.expires_at)
    expired_owner = OutlineVersionCreateService(
        **owner_ports, inputs=inputs(expired_reference),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    rejects("SOURCE_UNAVAILABLE", lambda: expired_owner.create(replace(
        command, idempotency_key="dual-scope-owner-global-expired-0001")))
    assert_rows(
        port=port, outline=outline, version=first.solution_outline_version_id,
        project=project, requirement=requirement,
        requirement_version=requirement_version,
        reference=created.reference_solution_id,
        reference_version=created.reference_version_id,
        scope="GLOBAL", actor=manager)
    assert qualified.deidentification_confirmation_id == confirmed.confirmation_id


if __name__ == "__main__":
    fixture.main(on_created=project_created)
    composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P03_P03_P04_A03_DUAL_SCOPE_OWNER_PG_PASS: "
          "PROJECT/GLOBAL actual Owner write with fixed Requirement/Reference, "
          "real source proof, replay, tamper/restriction/expiry rollback")
