"""Disposable Win11/PG proof of fixed Outline order/current source recheck."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineRequirementUseProofService,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.solution.application.create_outline_version import (
    CreateOutlineVersion,
    OutlineVersionCreateService,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef,
    OutlineRequirementRef,
    OutlineVersionDraftInput,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.prove_outline_section_use import (
    OutlineSectionUseProofService,
)
from plm_assistant.modules.solution.application.prove_outline_version_current import (
    OutlineVersionCurrentFactsService,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    SetReferenceEligibility,
)
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import (
    SqlAlchemyOutlineVersionCreateRepository,
)
from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.section_read_repository import (
    SqlAlchemySectionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = module(
    "outline_current_project_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
composition = module(
    "outline_current_reference_composition",
    "validation/sol-03-a04-p02-p03-reference-use-composition/verify.py")
previous = module(
    "outline_current_owner_fixture",
    "validation/sol-03-a04-p03-p03-p04-a03-outline-dual-scope-owner/verify.py")


def check(*, runtime, sources, audit, license_guard, project, manager,
          created, token, csrf, port, downloads, parse_results, **_unused):
    references, eligibility, _ = composition.services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 0, "ELIGIBLE", "Synthetic current source",
        "outline-current-source-eligible-0001"))
    outline, section = previous.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="current")
    requirement, requirement_version = previous.seed_approved_requirement(
        port=port, project=project, actor=manager, code="R-OUTLINE-CURRENT")
    owner = OutlineVersionCreateService(
        **previous.common(runtime=runtime, license_guard=license_guard, audit=audit),
        inputs=previous.inputs(references),
        repository=SqlAlchemyOutlineVersionCreateRepository())
    draft = OutlineVersionDraftInput(
        project, outline, (section,),
        (OutlineRequirementRef(requirement, requirement_version),),
        (OutlineReferenceRef("PROJECT", created.reference_solution_id,
                             created.reference_version_id),), (), ())
    first = owner.create(CreateOutlineVersion(
        token, csrf, uuid.uuid4(), draft, "outline-current-version-0001"))
    command = ValidateOutlineVersion(
        token, csrf, uuid.uuid4(), project, outline,
        first.solution_outline_version_id, "outline-current-check-0001")
    current = OutlineVersionCurrentFactsService(
        sections=OutlineSectionUseProofService(
            sections=SqlAlchemySectionReadRepository()),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        references=references)
    reads = SqlAlchemyOutlineVersionReadRepository()

    def observe():
        with runtime.unit_of_work() as tx:
            version = reads.get(
                tx, project_id=project, outline_id=outline,
                version_id=first.solution_outline_version_id)
            assert version is not None
            return current.facts(tx, command=command, version=version)

    before = observe()
    assert (before.order, before.source, before.coverage) == (
        "PASS", "PASS", "UNAVAILABLE"), before
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 1, "RESTRICTED", "Synthetic source revoked",
        "outline-current-source-restrict-0001"))
    after = observe()
    assert (after.order, after.source, after.coverage) == (
        "PASS", "UNAVAILABLE", "UNAVAILABLE"), after
    return 0


if __name__ == "__main__":
    fixture.main(on_created=check)
    print("SOL_03_A06_P03_A01_OUTLINE_CURRENT_PG_PASS: "
          "fixed version/current source, revocation fail-closed, coverage unavailable")
