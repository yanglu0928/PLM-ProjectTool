from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProofError,
    ApprovedSolutionInputProofService,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineRequirementRef,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery, OutlineVersionValidationFacts,
)
from plm_assistant.modules.solution.application.prove_outline_coverage import (
    CurrentOutlineCoverageProof,
)
from plm_assistant.modules.solution.application.read_outline import OutlineCurrentView
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.qualify_section_structured_spec import (
    QualifiedSectionStructuredSpec,
)


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def _fixed_review(project, outline, version, review_id, round_id, fingerprint, actor):
    reviewer = uuid.uuid4()
    progress = ReviewRoundProgress(round_id, NOW, (reviewer,)).record_decision(
        ReviewDecisionSnapshot(
            uuid.uuid4(), round_id, reviewer, ReviewDecisionKind.APPROVE, NOW,
        ),
    )
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "SOL-03", outline,
        "SOLUTION_OUTLINE_ALL_V1", "APPROVED", None, 2,
    )
    return FixedReviewRoundSnapshot(
        identity, 1, version, actor, progress, (uuid.uuid4(),), 1,
        uuid.uuid4(), fingerprint, 1, NOW, (), uuid.uuid4(), NOW, NOW,
    )


@pytest.fixture
def source():
    project, outline, outline_version, section, section_version = (
        uuid.uuid4() for _ in range(5)
    )
    actor, trace, review_id, round_id = (uuid.uuid4() for _ in range(4))
    req = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
    outline_fp, section_fp = b"o" * 32, b"s" * 32
    query = OutlineCurrentFactQuery(
        b"t" * 32, trace, project, outline, outline_version,
    )
    root = OutlineCurrentView(
        outline, project, "Solution", "ACTIVE", outline_version,
        actor, NOW, '"v3"',
    )
    version = OutlineVersionHistoryView(
        outline_version, outline, project, 3, "APPROVED", outline_fp,
        (section,), (req,), (), (), (), uuid.uuid4(), review_id,
        round_id, actor, NOW,
    )
    review = _fixed_review(
        project, outline, outline_version, review_id, round_id,
        outline_fp, actor,
    )
    section_history = SectionVersionHistoryView(
        section_version, section, project, 2, "APPROVED", "Section",
        uuid.uuid4(), None, section_fp, (), (), (), (), uuid.uuid4(),
        uuid.uuid4(), uuid.uuid4(), actor, NOW, "NONE_REQUIRED",
        "User decided no specialist design is required", (),
    )
    outlines, versions, reviews, current, coverage, sections, specs = (
        Mock() for _ in range(7)
    )
    outlines.get_current.return_value = root
    versions.get.return_value = version
    reviews.get_round.return_value = review
    current.facts.return_value = OutlineVersionValidationFacts(
        order="PASS", source="PASS", coverage="UNAVAILABLE",
    )
    coverage.prove.return_value = CurrentOutlineCoverageProof(
        project, outline, outline_version, (req,),
        (section_version,), b"r" * 32,
    )
    sections.get.return_value = section_history
    specs.prove_current.return_value = ()
    service = ApprovedSolutionInputProofService(
        outlines=outlines, versions=versions, reviews=reviews,
        current_facts=current, coverage=coverage,
        sections=sections, spec_qualification=specs,
    )
    return SimpleNamespace(**locals())


def test_proves_current_approved_outline_and_exact_section_inputs(source):
    s = source
    tx = object()
    proof = s.service.prove(tx, command=s.query)
    assert (proof.project_id, proof.outline_id, proof.outline_version_id) == (
        s.project, s.outline, s.outline_version,
    )
    assert proof.requirement_refs == (s.req,)
    assert [(item.section_id, item.section_version_id)
            for item in proof.sections] == [(s.section, s.section_version)]
    assert proof.sections[0].spec_binding_state == "NONE_REQUIRED"
    assert proof.requirement_scope_fingerprint == b"r" * 32
    assert s.current.facts.call_args.args[0] is tx
    assert s.coverage.prove.call_args.args[0] is tx
    assert s.sections.get.call_args.args[0] is tx


def test_stale_outline_pointer_and_wrong_terminal_review_fail_closed(source):
    s = source
    s.outlines.get_current.return_value = SimpleNamespace(
        project_id=s.project, solution_outline_id=s.outline,
        outline_state="ACTIVE", current_approved_version_ref=uuid.uuid4(),
    )
    with pytest.raises(ApprovedSolutionInputProofError):
        s.service.prove(object(), command=s.query)
    s.outlines.get_current.return_value = s.root
    s.reviews.get_round.return_value = None
    with pytest.raises(ApprovedSolutionInputProofError):
        s.service.prove(object(), command=s.query)
    s.coverage.prove.assert_not_called()


def test_undeclared_spec_binding_never_means_no_spec_required(source):
    s = source
    s.sections.get.return_value = SectionVersionHistoryView(
        s.section_version, s.section, s.project, 2, "APPROVED", "Section",
        uuid.uuid4(), None, b"s" * 32, (), (), (), (), uuid.uuid4(),
        uuid.uuid4(), uuid.uuid4(), s.actor, NOW,
    )
    with pytest.raises(ApprovedSolutionInputProofError):
        s.service.prove(object(), command=s.query)


def test_fixed_spec_refs_require_exact_current_qualification(source):
    s = source
    # Constructor is deliberately assembled from the immutable SectionVersion
    # payload; the qualification Owner is the authority for its approved refs.
    from plm_assistant.modules.solution.application.section_version_input import (
        SectionStructuredSpecRef,
    )
    spec_ref = SectionStructuredSpecRef(
        uuid.uuid4(), uuid.uuid4(), "fits the approved requirements",
    )
    s.sections.get.return_value = SectionVersionHistoryView(
        s.section_version, s.section, s.project, 2, "APPROVED", "Section",
        uuid.uuid4(), None, b"s" * 32, (), (), (), (), uuid.uuid4(),
        uuid.uuid4(), uuid.uuid4(), s.actor, NOW, "FIXED_REFS", None,
        (spec_ref,),
    )
    s.specs.prove_current.return_value = ()
    with pytest.raises(ApprovedSolutionInputProofError):
        s.service.prove(object(), command=s.query)
    s.specs.prove_current.assert_called_once()
    qualified = QualifiedSectionStructuredSpec(
        spec_ref, "STRUCTURED", b"p" * 32, uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), b"q" * 32, (),
    )
    s.specs.prove_current.return_value = (qualified,)
    proof = s.service.prove(object(), command=s.query)
    assert proof.sections[0].qualified_specs == (qualified,)
