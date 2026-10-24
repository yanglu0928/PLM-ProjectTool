"""Disposable Win11/PG18 approved Spec → Section candidate proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from plm_assistant.modules.review.infrastructure.read_repository import (
    SqlAlchemyReviewSnapshotReadRepository,
)
from plm_assistant.modules.solution.application.qualify_section_structured_spec import (
    SectionStructuredSpecQualificationError,
    SectionStructuredSpecQualificationService,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionStructuredSpecRef,
)
from plm_assistant.modules.solution.infrastructure.section_structured_spec_qualification_repository import (
    SqlAlchemySectionSpecCandidateRepository,
    SqlAlchemySectionSpecSourceRepository,
)
from plm_assistant.modules.solution.infrastructure.section_version_base import (
    SqlAlchemyCurrentSectionVersionBase,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "structured_spec_terminal_fixture",
    ROOT / "validation/sol-06-a15-p02-structured-spec-review-terminal-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _after_submit(*, runtime, project, other_project, draft,
                  approved_version, **context):
    prior.prior.on_http(
        runtime=runtime, project=project, other_project=other_project,
        draft=draft, approved_version=approved_version, **context)
    prior._terminal(
        "APPROVE", runtime=runtime, project=project,
        other_project=other_project, draft=draft,
        approved_version=approved_version, **context)
    candidates = SqlAlchemySectionSpecCandidateRepository()
    sections = SqlAlchemySectionSpecSourceRepository()
    qualifier = SectionStructuredSpecQualificationService(
        specs=candidates, sections=sections,
        reviews=SqlAlchemyReviewSnapshotReadRepository())
    with runtime.unit_of_work() as tx:
        spec = candidates.get(
            tx, project_id=project,
            spec_id=draft.structured_solution_spec_id)
        assert spec is not None and spec.section_refs
        source_ref = spec.section_refs[0]
        base = SqlAlchemyCurrentSectionVersionBase().current(
            tx, project_id=project,
            section_id=source_ref.solution_section_id)
        assert base is not None and base.next_version_no >= 2
        source = sections.get(
            tx, project_id=project,
            section_id=source_ref.solution_section_id,
            version_id=source_ref.solution_section_version_id)
        assert source is not None and source.requirement_refs
        ref = SectionStructuredSpecRef(
            spec.spec_series_id, spec.structured_solution_spec_id)
        (proof,) = qualifier.prove(
            tx, base=base, project_id=project,
            section_id=source_ref.solution_section_id,
            requirement_refs=source.requirement_refs,
            spec_refs=(ref,))
        assert proof.ref == ref
        assert proof.review_id == spec.review_ref
        assert proof.source_section_version_id == source_ref.solution_section_version_id
        assert proof.shared_requirement_version_ids
        assert sections.is_ancestor(
            tx, project_id=project,
            section_id=source_ref.solution_section_id,
            latest_version_id=base.supersedes_version_id,
            ancestor_version_id=source_ref.solution_section_version_id)
        assert not sections.is_ancestor(
            tx, project_id=project,
            section_id=source_ref.solution_section_id,
            latest_version_id=base.supersedes_version_id,
            ancestor_version_id=uuid.uuid4())
        try:
            qualifier.prove(
                tx, base=base, project_id=project,
                section_id=source_ref.solution_section_id,
                requirement_refs=source.requirement_refs,
                spec_refs=(SectionStructuredSpecRef(
                    spec.spec_series_id, approved_version),))
        except SectionStructuredSpecQualificationError:
            pass
        else:
            raise AssertionError("superseded Spec must not qualify")
        try:
            qualifier.prove(
                tx, base=base, project_id=other_project,
                section_id=source_ref.solution_section_id,
                requirement_refs=source.requirement_refs,
                spec_refs=(ref,))
        except SectionStructuredSpecQualificationError:
            pass
        else:
            raise AssertionError("cross-project Spec must not qualify")
    print("SOL_05_A04_P11_P04_P02_A01_SPEC_QUALIFICATION_PASS: actual Review "
          "APPROVED snapshot, current Spec, same-project source lineage and "
          "shared RequirementVersion; replaced/cross-project denied")


def _after_specs(*, created: dict[str, object], **specs):
    prior.prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"],
        member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.prior.on_review(
            **review, on_submit=_after_submit))


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                _after_specs(created=created, **specs))))
