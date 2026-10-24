"""CAP-01 GLOBAL Review metadata read never falls through PROJECT Scope."""

from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.capability.application.read_capability import CapabilityVersionView
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.review.application.global_capability_read import (
    GetGlobalCapabilityReview, GlobalCapabilityReviewReadError,
    GlobalCapabilityReviewReadService,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundProgress


class Transaction:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class GlobalCapabilityReviewReadTests(TestCase):
    def setUp(self):
        self.actor, self.review_id, self.round_id = uuid4(), uuid4(), uuid4()
        self.baseline_id, self.version_id, self.reviewer_id = uuid4(), uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        self.query = GetGlobalCapabilityReview(b"s" * 32, uuid4(), self.review_id)
        self.identity = ReviewIdentitySnapshot(
            self.review_id, "GLOBAL", None, "CAP-01", self.baseline_id,
            "DEPLOYMENT_ALL_V1", "IN_REVIEW", self.round_id, 1,
        )
        self.fixed = FixedReviewRoundSnapshot(
            self.identity, 1, self.version_id, self.actor,
            ReviewRoundProgress(self.round_id, self.now, (self.reviewer_id,)),
            (uuid4(),), 0, uuid4(), b"x" * 32, 1, self.now, (), uuid4(), self.now, None,
        )
        self.version = CapabilityVersionView(
            self.version_id, self.baseline_id, 1, "IN_REVIEW", "sha256:" + "a" * 64,
            "b" * 64, 1, 1, 1, None, self.review_id, self.round_id, self.now,
        )
        self.tx = Transaction()
        self.sessions, self.users, self.guard = Mock(), Mock(), Mock()
        self.reviews, self.capabilities = Mock(), Mock()
        self.sessions.authenticated_user.return_value = self.actor
        self.users.current_enabled_user.return_value = CurrentUserFacts(
            self.actor, "DEPLOYMENT_ADMIN",
        )
        self.reviews.get_review.return_value = self.identity
        self.reviews.get_single_global_round_id.return_value = self.round_id
        self.reviews.get_round.return_value = self.fixed
        self.capabilities.get_version.return_value = self.version

    def service(self):
        return GlobalCapabilityReviewReadService(
            unit_of_work=lambda: self.tx, sessions=self.sessions, users=self.users,
            license_guard=self.guard, reviews=self.reviews,
            capabilities=self.capabilities, clock=lambda: self.now,
        )

    def denied(self, code):
        with self.assertRaises(GlobalCapabilityReviewReadError) as caught:
            self.service().get(self.query)
        self.assertEqual(caught.exception.code, code)

    def test_admin_reads_exact_global_capability_review_and_binding(self):
        result = self.service().get(self.query)
        self.assertIs(result.review, self.identity)
        self.assertIs(result.fixed_round, self.fixed)
        self.assertEqual(result.review_etag, '"v1"')
        self.assertEqual(result.round_etag, '"v0"')
        self.reviews.get_review.assert_called_once_with(self.tx, "GLOBAL", None, self.review_id)
        self.reviews.get_round.assert_called_once_with(
            self.tx, "GLOBAL", None, self.review_id, self.round_id,
        )
        self.capabilities.get_version.assert_called_once_with(
            self.tx, visibility="ADMIN_HISTORY", baseline_id=self.baseline_id,
            baseline_version_id=self.version_id,
        )

    def test_unassigned_ordinary_user_cannot_probe_review(self):
        self.users.current_enabled_user.return_value = CurrentUserFacts(self.actor, "NONE")
        self.denied("RESOURCE_NOT_FOUND")
        self.capabilities.get_version.assert_not_called()

    def test_assigned_enabled_ordinary_reviewer_can_read(self):
        self.users.current_enabled_user.return_value = CurrentUserFacts(self.actor, "NONE")
        self.reviews.get_round.return_value = replace(
            self.fixed, progress=ReviewRoundProgress(self.round_id, self.now, (self.actor,)),
        )
        result = self.service().get(self.query)
        self.assertEqual(result.fixed_round.progress.reviewer_ids, (self.actor,))

    def test_disabled_user_cannot_probe_review(self):
        self.users.current_enabled_user.return_value = None
        self.denied("RESOURCE_NOT_FOUND")
        self.reviews.get_review.assert_not_called()

    def test_expired_session_cannot_read_review(self):
        self.sessions.authenticated_user.return_value = None
        self.denied("AUTH_ACCESS_DENIED")
        self.reviews.get_review.assert_not_called()

    def test_non_capability_and_project_scope_do_not_fall_through(self):
        self.reviews.get_review.return_value = replace(self.identity, subject_type="HND-01")
        self.denied("RESOURCE_NOT_FOUND")
        self.reviews.get_round.assert_not_called()
        self.reviews.get_review.return_value = replace(
            self.identity, scope="PROJECT", project_id=uuid4(),
        )
        self.denied("RESOURCE_NOT_FOUND")

    def test_wrong_subject_version_or_review_binding_is_denied(self):
        self.capabilities.get_version.return_value = replace(
            self.version, review_ref=uuid4(),
        )
        self.denied("RESOURCE_NOT_FOUND")
        self.capabilities.get_version.return_value = replace(
            self.version, baseline_version_id=uuid4(),
        )
        self.denied("RESOURCE_NOT_FOUND")

    def test_missing_or_multiple_rounds_fail_closed(self):
        self.reviews.get_single_global_round_id.return_value = None
        self.denied("GLOBAL_REVIEW_UNAVAILABLE")
        self.reviews.get_round.assert_not_called()

    def test_license_refusal_precedes_review_read(self):
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        self.denied("LICENSE_OPERATION_DENIED")
        self.sessions.authenticated_user.assert_not_called()

    def test_invalid_command_fails_without_license_or_db(self):
        with self.assertRaises(GlobalCapabilityReviewReadError) as caught:
            self.service().get(replace(self.query, session_token=b"short"))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
