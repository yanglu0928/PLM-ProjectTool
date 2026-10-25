"""Disposable Win11 PG/real-file proof of current OutlineVersion inputs."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution, ReferenceCreateService
from plm_assistant.modules.solution.application.create_section import CreateSection, SectionCreateService
from plm_assistant.modules.solution.application.outline_version_input import OutlineReferenceRef, OutlineRequirementRef, OutlineVersionDraftInput
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseProofService
from plm_assistant.modules.solution.application.prove_outline_version_input import OutlineVersionInputProofError, OutlineVersionInputProofService
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.solution.application.set_reference_eligibility import SetReferenceEligibility
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_version_base import SqlAlchemyCurrentOutlineVersionBase
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = module(
    "outline_input_project_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
composition = module(
    "outline_input_reference_composition",
    "validation/sol-03-a04-p02-p03-reference-use-composition/verify.py")


def denied(action):
    try:
        action()
    except OutlineVersionInputProofError:
        return
    raise AssertionError("unavailable OutlineVersion source accepted")


def on_created(*, runtime, sources, audit, license_guard,
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
        "outline-input-proof-eligibility-0001"))
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    outline = OutlineCreateService(
        **common, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          "Proof outline", "outline-input-proof-root-0001"))
    section = SectionCreateService(
        **common, repository=SqlAlchemySectionCreateRepository()).create(
            CreateSection(token, csrf, uuid.uuid4(), project,
                          outline.solution_outline_id, "Overview",
                          "outline-input-proof-section-0001"))
    requirement, version = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,"
            "requirement_code,requirement_code_normalized,requirement_state,"
            "current_approved_version_ref,created_by) "
            "VALUES (%s,%s,'R-OUTLINE-PROOF','R-OUTLINE-PROOF','ACTIVE',%s,%s)",
            (requirement, project, version, manager))
        db.execute(
            "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
            "requirement_id,project_id,version_no,version_state,statement,"
            "rationale,domain_name,priority,risk,requirement_classification,"
            "content_fingerprint,declared_source_count,declared_acceptance_count,"
            "declared_capability_count,declared_assumption_count,"
            "declared_exclusion_count,declared_dependency_count,"
            "declared_ai_task_count,review_ref,review_round_ref,created_by) "
            "VALUES (%s,%s,%s,1,'APPROVED','Synthetic input',"
            "'Synthetic rationale','Domain','HIGH','LOW','STANDARD_FUNCTION',"
            "%s,1,0,0,0,0,0,0,%s,%s,%s)",
            (version, requirement, project, b"r" * 32,
             uuid.uuid4(), uuid.uuid4(), manager))
    proof = OutlineVersionInputProofService(
        bases=SqlAlchemyCurrentOutlineVersionBase(),
        sections=OutlineSectionUseProofService(sections=SqlAlchemySectionReadRepository()),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        references=references)
    draft = OutlineVersionDraftInput(
        project, outline.solution_outline_id, (section.solution_section_id,),
        (OutlineRequirementRef(requirement, version),),
        (OutlineReferenceRef("PROJECT", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    trace = uuid.uuid4()
    with runtime.unit_of_work() as tx:
        result = proof.prove(tx, trace_id=trace, draft=draft)
        assert result.next_version_no == 1 and result.supersedes_version_id is None
        assert len(result.content_fingerprint) == 32
        denied(lambda: proof.prove(tx, trace_id=trace, draft=OutlineVersionDraftInput(
            other_project, outline.solution_outline_id, draft.section_ids,
            draft.requirement_refs, draft.reference_refs, (), ())))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            try:
                db.execute(
                    "SELECT solution_outline_id FROM plm.sol_outlines "
                    "WHERE solution_outline_id=%s FOR UPDATE NOWAIT",
                    (outline.solution_outline_id,))
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("Outline base lock not retained")
    file = scratch / "private-documents" / locator
    original = file.read_bytes()
    try:
        file.write_bytes(b"X" * len(content))
        with runtime.unit_of_work() as tx:
            denied(lambda: proof.prove(tx, trace_id=trace, draft=draft))
    finally:
        file.write_bytes(original)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 1, "RESTRICTED", "No longer current",
        "outline-input-proof-restrict-0002"))
    with runtime.unit_of_work() as tx:
        denied(lambda: proof.prove(tx, trace_id=trace, draft=draft))
    return 0


def global_qualified(*, runtime, request, sources, audit, license_guard,
                     downloads, parse_results, confirmed, qualified, port,
                     **_unused):
    references, eligibility, common = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    created = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(
                request, composition.global_fixture.CSRF,
                "Global input reference", "outline-input-global-create-0001"))
    eligibility.set(SetReferenceEligibility(
        composition.global_fixture.TOKEN, composition.global_fixture.CSRF,
        uuid.uuid4(), "GLOBAL", None, created.reference_solution_id,
        0, "ELIGIBLE", "Global source reviewed",
        "outline-input-global-eligible-0001"))
    project, outline, section, requirement, version = (
        uuid.uuid4() for _ in range(5))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        actor = db.execute("SELECT user_id FROM plm.auth_users LIMIT 1").fetchone()[0]
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.prj_projects(project_id,project_code,"
            "project_code_normalized,name,created_by) "
            "VALUES (%s,'SOLINPUTGLOBAL','solinputglobal','Global target',%s)",
            (project, actor))
        db.execute(
            "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,"
            "created_by) VALUES (%s,%s,'Global target outline',%s)",
            (outline, project, actor))
        db.execute(
            "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
            "project_id,section_key,created_by) VALUES (%s,%s,%s,'Overview',%s)",
            (section, outline, project, actor))
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,"
            "requirement_code,requirement_code_normalized,requirement_state,"
            "current_approved_version_ref,created_by) "
            "VALUES (%s,%s,'R-GLOBAL-INPUT','R-GLOBAL-INPUT','ACTIVE',%s,%s)",
            (requirement, project, version, actor))
        db.execute(
            "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
            "requirement_id,project_id,version_no,version_state,statement,"
            "rationale,domain_name,priority,risk,requirement_classification,"
            "content_fingerprint,declared_source_count,declared_acceptance_count,"
            "declared_capability_count,declared_assumption_count,"
            "declared_exclusion_count,declared_dependency_count,"
            "declared_ai_task_count,review_ref,review_round_ref,created_by) "
            "VALUES (%s,%s,%s,1,'APPROVED','Synthetic global target',"
            "'Synthetic rationale','Domain','HIGH','LOW','STANDARD_FUNCTION',"
            "%s,1,0,0,0,0,0,0,%s,%s,%s)",
            (version, requirement, project, b"g" * 32,
             uuid.uuid4(), uuid.uuid4(), actor))
    proof = OutlineVersionInputProofService(
        bases=SqlAlchemyCurrentOutlineVersionBase(),
        sections=OutlineSectionUseProofService(sections=SqlAlchemySectionReadRepository()),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        references=references)
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, version),),
        (OutlineReferenceRef("GLOBAL", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    with runtime.unit_of_work() as tx:
        result = proof.prove(tx, trace_id=uuid.uuid4(), draft=draft)
        assert len(result.content_fingerprint) == 32
        assert result.draft.project_id == project
    expired = ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=references._sources,
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository(),
        clock=lambda: confirmed.expires_at)
    expired_proof = OutlineVersionInputProofService(
        bases=SqlAlchemyCurrentOutlineVersionBase(),
        sections=OutlineSectionUseProofService(sections=SqlAlchemySectionReadRepository()),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        references=expired)
    with runtime.unit_of_work() as tx:
        denied(lambda: expired_proof.prove(tx, trace_id=uuid.uuid4(), draft=draft))
    assert result.content_fingerprint != qualified.content_fingerprint


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P03_P03_P03_OUTLINE_INPUT_PROOF_PASS: real PROJECT/GLOBAL "
          "Section/Requirement/Reference, source files, isolation, tamper, "
          "eligibility/confirmation time and retained Outline lock")
