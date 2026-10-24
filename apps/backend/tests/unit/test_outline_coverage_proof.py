"""Complete Outline coverage uses current scope, approved Sections and Review."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plm_assistant.modules.requirement.application.approved_inventory import (
    ApprovedRequirementInventory,
    ApprovedRequirementInventoryError,
    CurrentApprovedRequirement,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundProgress,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineRequirementRef,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery,
    ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.prove_outline_coverage import (
    OutlineCoverageProofError,
    OutlineCoverageProofService,
)
from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    SectionVersionValidationFacts,
)


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
PASS = SectionVersionValidationFacts(*(["PASS"] * 6))


def _review(project, section, version, fingerprint, actor):
    review_id, round_id, reviewer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    progress = ReviewRoundProgress(round_id, NOW, (reviewer,)).record_decision(
        ReviewDecisionSnapshot(uuid.uuid4(), round_id, reviewer,
                               ReviewDecisionKind.APPROVE, NOW),
    )
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "SOL-05", section,
        "SOLUTION_SECTION_ALL_V1", "APPROVED", None, 2,
    )
    fixed = FixedReviewRoundSnapshot(
        identity, 1, version, actor, progress, (uuid.uuid4(),), 1,
        uuid.uuid4(), fingerprint, 1, NOW, (), uuid.uuid4(), NOW, NOW,
    )
    return review_id, round_id, fixed


@pytest.fixture
def setup():
    project, outline, outline_version, section, section_version = (
        uuid.uuid4() for _ in range(5)
    )
    actor, trace, document = (uuid.uuid4() for _ in range(3))
    requirement = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
    review_id, round_id, fixed_review = _review(
        project, section, section_version, b"f" * 32, actor,
    )
    section_view = SectionCurrentView(
        section, outline, project, "Body", "ACTIVE", section_version,
        actor, NOW, '"v2"',
    )
    version_view = SectionVersionHistoryView(
        section_version, section, project, 1, "APPROVED", "Body",
        document, None, b"f" * 32,
        (SectionRequirementRef(
            requirement.requirement_id, requirement.requirement_version_id,
        ),), (), (), (), None, review_id, round_id, actor, NOW,
        "NONE_REQUIRED", "No specialist design required", (),
    )
    outline_view = OutlineVersionHistoryView(
        outline_version, outline, project, 1, "DRAFT", b"o" * 32,
        (section,), (requirement,), (), (), (), None, None, None,
        actor, NOW,
    )
    command = ValidateOutlineVersion(
        b"s" * 32, b"c" * 32, trace, project, outline,
        outline_version, "outline-coverage-0001",
    )
    inventory_value = ApprovedRequirementInventory(
        project, 1,
        (CurrentApprovedRequirement(
            requirement.requirement_id, requirement.requirement_version_id,
            b"r" * 32, uuid.uuid4(), uuid.uuid4(),
        ),), (), b"i" * 32,
    )
    inventory, sections, versions, reviews, current = (
        Mock() for _ in range(5)
    )
    inventory.prove_in_transaction.return_value = inventory_value
    sections.get_current.return_value = section_view
    versions.get.return_value = version_view
    reviews.get_round.return_value = fixed_review
    current.facts.return_value = PASS
    service = OutlineCoverageProofService(
        inventory=inventory, sections=sections, versions=versions,
        reviews=reviews, current=current,
    )
    return SimpleNamespace(**locals())


def _prove(s, *, outline=None):
    return s.service.prove(
        s.tx, command=s.command, version=outline or s.outline_view,
    )


def test_complete_current_approved_section_union_uses_same_transaction(setup):
    s = setup
    s.tx = object()
    proof = _prove(s)
    assert proof.requirement_refs == (s.requirement,)
    assert proof.section_version_ids == (s.section_version,)
    assert proof.requirement_scope_fingerprint == b"i" * 32
    s.inventory.prove_in_transaction.assert_called_once()
    tx, query = s.inventory.prove_in_transaction.call_args.args
    assert tx is s.tx
    assert (query.session_token, query.trace_id, query.project_id) == (
        s.command.session_token, s.trace, s.project,
    )
    s.current.facts.assert_called_once()
    assert s.current.facts.call_args.args[0] is s.tx
    assert s.current.facts.call_args.kwargs["version"] is s.version_view


def test_internal_review_query_reproves_in_review_but_public_validate_does_not(setup):
    s = setup
    s.tx = object()
    in_review = replace(s.outline_view, version_state="IN_REVIEW",
                        review_ref=uuid.uuid4(), review_round_ref=uuid.uuid4())
    internal = OutlineCurrentFactQuery(
        s.command.session_token, s.trace, s.project, s.outline,
        s.outline_version)
    proof = s.service.prove(s.tx, command=internal, version=in_review)
    assert proof.solution_outline_version_id == s.outline_version
    assert s.inventory.prove_in_transaction.call_args.args[0] is s.tx
    with pytest.raises(OutlineCoverageProofError):
        s.service.prove(s.tx, command=s.command, version=in_review)
    with pytest.raises(OutlineCoverageProofError):
        s.service.prove(s.tx, command=replace(internal, project_id=uuid.uuid4()),
                        version=in_review)


def test_fixed_outline_must_equal_complete_approved_requirement_scope(setup):
    s = setup
    s.tx = object()
    other = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
    s.inventory.prove_in_transaction.return_value = replace(
        s.inventory_value, root_count=2,
        approved=(*s.inventory_value.approved,
                  CurrentApprovedRequirement(other.requirement_id,
                                             other.requirement_version_id,
                                             b"x" * 32, uuid.uuid4(), uuid.uuid4())),
    )
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "SOLUTION_COVERAGE_INCOMPLETE"
    s.sections.get_current.assert_not_called()
    # Generic missing declarations cannot waive the unlisted formal version.
    with pytest.raises(OutlineCoverageProofError):
        _prove(s, outline=replace(s.outline_view,
                                  missing_declarations=({"reason": "skip"},)))


def test_section_coverage_gap_or_out_of_scope_ref_fails(setup):
    s = setup
    s.tx = object()
    s.versions.get.return_value = replace(s.version_view, requirement_refs=())
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "SOLUTION_COVERAGE_INCOMPLETE"
    s.versions.get.return_value = replace(
        s.version_view, requirement_refs=(SectionRequirementRef(
            uuid.uuid4(), uuid.uuid4()),),
    )
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "SOLUTION_COVERAGE_INCOMPLETE"


def test_two_approved_sections_cover_union_without_requiring_unique_owner(setup):
    s = setup
    s.tx = object()
    other = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
    other_section, other_version = uuid.uuid4(), uuid.uuid4()
    second_review, second_round, second_fixed = _review(
        s.project, other_section, other_version, b"g" * 32, s.actor,
    )
    second_section = replace(
        s.section_view, solution_section_id=other_section,
        current_approved_version_ref=other_version,
    )
    second_version = replace(
        s.version_view, solution_section_id=other_section,
        solution_section_version_id=other_version,
        content_fingerprint=b"g" * 32,
        review_ref=second_review, review_round_ref=second_round,
        requirement_refs=(
            SectionRequirementRef(s.requirement.requirement_id,
                                  s.requirement.requirement_version_id),
            SectionRequirementRef(other.requirement_id,
                                  other.requirement_version_id),
        ),
    )
    s.inventory.prove_in_transaction.return_value = replace(
        s.inventory_value, root_count=2,
        approved=(*s.inventory_value.approved,
                  CurrentApprovedRequirement(other.requirement_id,
                                             other.requirement_version_id,
                                             b"x" * 32, uuid.uuid4(), uuid.uuid4())),
    )
    s.sections.get_current.side_effect = lambda _tx, *, project_id, section_id: (
        s.section_view if section_id == s.section else second_section
    )
    s.versions.get.side_effect = lambda _tx, *, project_id, section_id, version_id: (
        s.version_view if section_id == s.section else second_version
    )
    s.reviews.get_round.side_effect = lambda _tx, _scope, _project, review_id, _round: (
        s.fixed_review if review_id == s.review_id else second_fixed
    )
    outline = replace(
        s.outline_view, section_ids=(s.section, other_section),
        requirement_refs=(s.requirement, other),
    )
    proof = _prove(s, outline=outline)
    assert proof.section_version_ids == (s.section_version, other_version)
    assert proof.requirement_refs == (s.requirement, other)


def test_missing_approved_pointer_wrong_project_or_review_fails_closed(setup):
    s = setup
    s.tx = object()
    for current_section in (
        replace(s.section_view, current_approved_version_ref=None),
        replace(s.section_view, project_id=uuid.uuid4()),
        replace(s.section_view, solution_outline_id=uuid.uuid4()),
    ):
        s.sections.get_current.return_value = current_section
        with pytest.raises(OutlineCoverageProofError):
            _prove(s)
    s.sections.get_current.return_value = s.section_view
    s.versions.get.return_value = replace(s.version_view,
                                          solution_section_version_id=uuid.uuid4())
    with pytest.raises(OutlineCoverageProofError):
        _prove(s)
    s.versions.get.return_value = s.version_view
    s.reviews.get_round.return_value = replace(
        s.fixed_review, subject_fingerprint=b"z" * 32,
    )
    with pytest.raises(OutlineCoverageProofError):
        _prove(s)
    s.reviews.get_round.return_value = replace(
        s.fixed_review, review=replace(s.fixed_review.review,
                                       subject_id=uuid.uuid4()),
    )
    with pytest.raises(OutlineCoverageProofError):
        _prove(s)


def test_trace_failure_and_unknown_spec_never_pass(setup):
    s = setup
    s.tx = object()
    s.current.facts.return_value = replace(PASS, trace="FAIL")
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "SOLUTION_COVERAGE_INCOMPLETE"
    s.current.facts.return_value = replace(PASS, spec="UNAVAILABLE")
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "SOLUTION_COVERAGE_UNAVAILABLE"


def test_unavailable_inventory_or_wrong_outline_denies_before_section(setup):
    s = setup
    s.tx = object()
    s.inventory.prove_in_transaction.side_effect = (
        ApprovedRequirementInventoryError("AUTH_ACCESS_DENIED"))
    with pytest.raises(OutlineCoverageProofError) as caught:
        _prove(s)
    assert caught.value.code == "AUTH_ACCESS_DENIED"
    s.sections.get_current.assert_not_called()
    with pytest.raises(OutlineCoverageProofError):
        s.service.prove(None, command=s.command, version=s.outline_view)
    with pytest.raises(OutlineCoverageProofError):
        _prove(s, outline=replace(s.outline_view, project_id=uuid.uuid4()))
