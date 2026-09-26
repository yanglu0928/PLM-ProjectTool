from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import unittest
from plm_assistant.modules.review.application.read_snapshot import ReviewBasisObservation, ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_start import ReviewSubjectStartRequest, PreparedReviewSubject, ReviewSubjectStartError


class SubjectStartTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        identity = ReviewIdentitySnapshot(uuid4(), "PROJECT", uuid4(), "HND-02", uuid4(), "CUSTOMER_ALL_V1", "DRAFT", None, 0)
        self.request = ReviewSubjectStartRequest(uuid4(), identity, uuid4(), uuid4(), (uuid4(), uuid4()))
        self.ref = ReviewBasisObservation("EVIDENCE", uuid4(), "PROJECT", identity.project_id, "ELIGIBLE", 1, b"e"*32, self.now)
        self.ready = PreparedReviewSubject(self.request, b"s"*32, 1, self.now, self.request.reviewer_ids, (self.ref,))

    def test_immutable_explicit_binding_not_owner_implementation(self):
        self.ready.require_binding(self.request)
        with self.assertRaises(FrozenInstanceError): self.ready.content_fingerprint = b"x"*32

    def test_request_scope_active_round_and_duplicate_reviewers_rejected(self):
        root = self.request.review
        for changes in (dict(actor_id=None), dict(round_id=True), dict(subject_version_id=None), dict(reviewer_ids=()),
                        dict(reviewer_ids=self.request.reviewer_ids*2), dict(reviewer_ids=list(self.request.reviewer_ids)),
                        dict(review=replace(root, scope="GLOBAL", project_id=None)),
                        dict(review=replace(root, state="IN_REVIEW", active_round_id=uuid4(), lock_version=1))):
            with self.subTest(changes=changes), self.assertRaises(ReviewSubjectStartError): replace(self.request, **changes)

    def test_every_request_dimension_bound_no_reusing_other_subject_or_round(self):
        for changes in (dict(actor_id=uuid4()), dict(round_id=uuid4()), dict(subject_version_id=uuid4()),
                        dict(reviewer_ids=tuple(reversed(self.request.reviewer_ids))),
                        dict(review=replace(self.request.review, review_id=uuid4())),
                        dict(review=replace(self.request.review, subject_id=uuid4())),
                        dict(review=replace(self.request.review, policy_code="OTHER_V1")),
                        dict(review=replace(self.request.review, project_id=uuid4()))):
            with self.subTest(changes=changes), self.assertRaises(ReviewSubjectStartError): self.ready.require_binding(replace(self.request, **changes))

    def test_fixed_values_and_complete_reviewer_set_required(self):
        for changes in (dict(content_fingerprint=b"x"), dict(proof_schema_version=True), dict(proof_schema_version=2),
                        dict(verified_at=datetime.now()), dict(qualified_reviewer_ids=self.request.reviewer_ids[:1]),
                        dict(qualified_reviewer_ids=list(self.request.reviewer_ids)), dict(basis=list(self.ready.basis)), dict(request=True)):
            with self.subTest(changes=changes), self.assertRaises(ReviewSubjectStartError): replace(self.ready, **changes)

    def test_source_scope_duplicate_and_observation_chronology(self):
        trace = replace(self.ref, ref_kind="TRACE_LINK", observed_state="ACTIVE", observed_lock_version=0)
        for basis in ((self.ref,self.ref), (replace(self.ref, ref_project_id=uuid4()),),
                      (replace(trace, ref_scope="GLOBAL", ref_project_id=None),),
                      (replace(self.ref, verified_at=self.now+timedelta(seconds=1)),)):
            with self.assertRaises(ReviewSubjectStartError): replace(self.ready, basis=basis)
        replace(self.ready, basis=(replace(self.ref, ref_scope="GLOBAL", ref_project_id=None), trace))
        # Empty refs can be structurally represented; actual Owner must enforce
        # version-type-specific required source coverage, not a DTO heuristic.
        replace(self.ready, basis=())

    def test_safe_error_and_terminal_old_identity_allowed_only_for_owner_recheck(self):
        old = replace(self.request.review, state="RETURNED", lock_version=3)
        replace(self.request, review=old)
        self.assertEqual(str(ReviewSubjectStartError()), "Review Subject start unavailable")
