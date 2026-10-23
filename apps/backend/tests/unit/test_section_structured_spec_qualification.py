from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.solution.application.qualify_section_structured_spec import (
    SectionCurrentSpecQualificationService,
    SectionStructuredSpecQualificationError,
    SectionStructuredSpecQualificationService,
)
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecHistoryView,
)
from plm_assistant.modules.solution.application.section_version_base import (
    CurrentSectionVersionBase,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef, SectionStructuredSpecRef,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef,
)


class _Specs:
    def __init__(self, view):
        self.view = view
        self.approved = view.structured_solution_spec_id
        self.calls = []

    def get(self, tx, *, project_id, spec_id):
        self.calls.append((tx, project_id, spec_id))
        return self.view

    def current_approved(self, tx, *, project_id, series_id):
        self.calls.append((tx, project_id, series_id))
        return self.approved


class _Sections:
    def __init__(self, view):
        self.view = view
        self.ancestor = True
        self.calls = []

    def get(self, tx, *, project_id, section_id, version_id):
        self.calls.append((tx, project_id, section_id, version_id))
        return self.view

    def is_ancestor(self, tx, *, project_id, section_id,
                    latest_version_id, ancestor_version_id):
        self.calls.append((tx, project_id, section_id,
                           latest_version_id, ancestor_version_id))
        return self.ancestor


class _Reviews:
    def __init__(self, identity, fixed):
        self.identity, self.fixed = identity, fixed
        self.calls = []

    def get_review(self, tx, scope, project_id, review_id):
        self.calls.append((tx, scope, project_id, review_id))
        return self.identity

    def get_round(self, tx, scope, project_id, review_id, round_id):
        self.calls.append((tx, scope, project_id, review_id, round_id))
        return self.fixed


class SectionStructuredSpecQualificationTests(unittest.TestCase):
    def setUp(self):
        (self.project, self.outline, self.section, self.source_id,
         self.latest_id, self.series, self.spec_id, self.review_id,
         self.round_id, self.actor, self.requirement,
         self.requirement_version) = (uuid.uuid4() for _ in range(12))
        self.tx = object()
        self.now = datetime(2026, 10, 23, tzinfo=timezone.utc)
        self.ref = SectionStructuredSpecRef(self.series, self.spec_id)
        self.base = CurrentSectionVersionBase(
            self.project, self.outline, self.section, 3,
            self.latest_id, 0, 0)
        self.requirements = (SectionRequirementRef(
            self.requirement, self.requirement_version),)
        self.source = SectionVersionHistoryView(
            self.source_id, self.section, self.project, 1, "SUPERSEDED",
            "Prior section", uuid.uuid4(), None, b"s" * 32,
            self.requirements, (), (), (), None,
            self.review_id, self.round_id, self.actor, self.now)
        other_requirement, other_version = uuid.uuid4(), uuid.uuid4()
        self.spec = StructuredSpecHistoryView(
            self.spec_id, self.series, self.project, "PROCESS_MODEL", 1,
            "APPROVED", b"p" * 32, b"{}", b"q" * 32,
            (SpecRequirementRef(self.requirement, self.requirement_version),
             SpecRequirementRef(other_requirement, other_version)),
            (SpecSectionRef(self.section, self.source_id),
             SpecSectionRef(uuid.uuid4(), uuid.uuid4())),
            (), (), None, self.review_id, self.round_id,
            self.actor, self.now)
        reviewer = uuid.uuid4()
        self.identity = ReviewIdentitySnapshot(
            self.review_id, "PROJECT", self.project, "SOL-06", self.series,
            "STRUCTURED_SPEC_ALL_V1", "APPROVED", None, 2)
        progress = ReviewRoundProgress(
            self.round_id, self.now, (reviewer,),
            (ReviewDecisionSnapshot(uuid.uuid4(), self.round_id,
                                    reviewer, ReviewDecisionKind.APPROVE,
                                    self.now),))
        self.fixed = FixedReviewRoundSnapshot(
            self.identity, 1, self.spec_id, self.actor, progress,
            (uuid.uuid4(),), 1, uuid.uuid4(), b"p" * 32, 1,
            self.now, (), uuid.uuid4(), self.now, self.now)
        self.specs = _Specs(self.spec)
        self.sections = _Sections(self.source)
        self.reviews = _Reviews(self.identity, self.fixed)
        self.service = SectionStructuredSpecQualificationService(
            specs=self.specs, sections=self.sections, reviews=self.reviews)

    def prove(self, **changes):
        values = dict(transaction=self.tx, base=self.base,
                      project_id=self.project, section_id=self.section,
                      requirement_refs=self.requirements, spec_refs=(self.ref,))
        values.update(changes)
        return self.service.prove(**values)

    def denied(self, **changes):
        with self.assertRaisesRegex(SectionStructuredSpecQualificationError,
                                    "SOURCE_UNAVAILABLE"):
            self.prove(**changes)

    def test_current_approved_cross_section_spec_with_shared_requirement(self):
        (proof,) = self.prove()
        self.assertEqual(proof.ref, self.ref)
        self.assertEqual(proof.source_section_version_id, self.source_id)
        self.assertEqual(proof.shared_requirement_version_ids,
                         (self.requirement_version,))
        self.assertEqual(proof.review_id, self.review_id)
        self.assertTrue(all(call[0] is self.tx for call in (
            *self.specs.calls, *self.sections.calls, *self.reviews.calls)))
        self.assertNotIn("Prior section", repr(proof))

    def test_rejects_unapproved_replaced_cross_project_or_wrong_series(self):
        for change in (
            dict(view=replace(self.spec, version_state="DRAFT")),
            dict(view=replace(self.spec, version_state="SUPERSEDED")),
            dict(view=replace(self.spec, project_id=uuid.uuid4())),
            dict(view=replace(self.spec, spec_series_id=uuid.uuid4())),
            dict(view=replace(self.spec, review_ref=None,
                              review_round_ref=None)),
        ):
            with self.subTest(change=change):
                self.specs.view = change["view"]
                self.denied()
        self.specs.view = self.spec
        self.specs.approved = uuid.uuid4()
        self.denied()

    def test_rejects_review_mismatch_or_not_approved(self):
        for wrong in (
            replace(self.identity, state="RETURNED"),
            replace(self.identity, subject_id=uuid.uuid4()),
            replace(self.identity, policy_code="OTHER_POLICY"),
            None,
        ):
            with self.subTest(wrong=wrong):
                self.reviews.identity = wrong
                self.denied()
        self.reviews.identity = self.identity
        for wrong in (
            replace(self.fixed, subject_version_id=uuid.uuid4()),
            replace(self.fixed, subject_fingerprint=b"x" * 32),
            None,
        ):
            with self.subTest(wrong=wrong):
                self.reviews.fixed = wrong
                self.denied()

    def test_rejects_wrong_source_lineage_or_unshared_requirements(self):
        self.specs.view = replace(self.spec, section_refs=(
            SpecSectionRef(uuid.uuid4(), uuid.uuid4()),))
        self.denied()
        self.specs.view = self.spec
        for wrong in (
            replace(self.source, version_state="RETURNED"),
            replace(self.source, version_state="RESTRICTED"),
            replace(self.source, project_id=uuid.uuid4()),
            replace(self.source, version_no=3),
            None,
        ):
            with self.subTest(wrong=wrong):
                self.sections.view = wrong
                self.denied()
        self.sections.view = self.source
        self.sections.ancestor = False
        self.denied()
        self.sections.ancestor = True
        self.denied(requirement_refs=(SectionRequirementRef(
            uuid.uuid4(), uuid.uuid4()),))

    def test_rejects_invalid_request_before_ports(self):
        for change in (
            dict(transaction=None),
            dict(project_id=uuid.uuid4()),
            dict(base=replace(self.base, next_version_no=1,
                              supersedes_version_id=None)),
            dict(spec_refs=()),
            dict(spec_refs=(self.ref, self.ref)),
            dict(requirement_refs=(self.requirements[0],
                                   self.requirements[0])),
        ):
            with self.subTest(change=change):
                self.denied(**change)
        self.assertEqual(self.specs.calls, [])

    def test_current_draft_rechecks_approved_spec_at_fixed_predecessor(self):
        ref = replace(self.ref, fit_rationale="Author fit for current section")
        target = replace(
            self.source, solution_section_version_id=uuid.uuid4(),
            version_no=2, version_state="DRAFT",
            supersedes_version_ref=self.latest_id,
            spec_binding_state="FIXED_REFS", structured_spec_refs=(ref,))
        current = SectionCurrentSpecQualificationService(self.service)
        (proof,) = current.prove(self.tx, version=target)
        self.assertEqual(proof.ref, ref)
        self.assertEqual(proof.shared_requirement_version_ids,
                         (self.requirement_version,))
        self.assertIn((self.tx, self.project, self.section,
                       self.latest_id, self.source_id), self.sections.calls)
        self.specs.approved = uuid.uuid4()
        with self.assertRaises(SectionStructuredSpecQualificationError):
            current.prove(self.tx, version=target)

    def test_current_draft_missing_basis_or_non_draft_denied_before_ports(self):
        ref = replace(self.ref, fit_rationale="Author fit")
        target = replace(
            self.source, solution_section_version_id=uuid.uuid4(),
            version_no=2, version_state="DRAFT",
            supersedes_version_ref=self.latest_id,
            spec_binding_state="FIXED_REFS", structured_spec_refs=(ref,))
        current = SectionCurrentSpecQualificationService(self.service)
        for wrong in (
            replace(target, structured_spec_refs=(self.ref,)),
            replace(target, structured_spec_refs=(replace(ref,
                    fit_rationale=" padded"),)),
            replace(target, version_state="APPROVED"),
            replace(target, supersedes_version_ref=None),
        ):
            with self.subTest(wrong=wrong):
                with self.assertRaises(SectionStructuredSpecQualificationError):
                    current.prove(self.tx, version=wrong)
        self.assertEqual(self.specs.calls, [])
        with self.assertRaises(SectionStructuredSpecQualificationError):
            current.prove(self.tx, version=replace(target, requirement_refs=()))


if __name__ == "__main__":
    unittest.main()
