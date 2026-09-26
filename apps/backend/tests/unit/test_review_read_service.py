from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import Mock
import unittest

from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, AuthorizedProjectAction, ProjectAuthorizationError,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead, ReviewReadError, ReviewReadQuery, ReviewReadService,
)
from plm_assistant.modules.review.application.read_snapshot import FixedReviewRoundSnapshot, ReviewIdentitySnapshot
from plm_assistant.modules.review.domain.round_progress import ReviewRoundProgress


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class ReviewReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.review, self.round, self.version = (uuid4() for _ in range(5))
        self.query = ReviewReadQuery(b"s"*32, self.project, self.review, uuid4(), self.round)
        self.now = datetime.now(timezone.utc)
        self.identity = ReviewIdentitySnapshot(self.review, "PROJECT", self.project, "HND-02", uuid4(),
                                               "CUSTOMER_ALL_V1", "IN_REVIEW", self.round, 1)
        self.fixed = FixedReviewRoundSnapshot(self.identity, 1, self.version, self.actor,
            ReviewRoundProgress(self.round, self.now, (uuid4(),)), (uuid4(),), 0,
            uuid4(), b"s"*32, 1, self.now, (), uuid4(), self.now, None)
        self.tx = Tx()
        self.sessions = Mock()
        self.sessions.authenticated_user.return_value = self.actor
        self.projects = Mock()
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(self.actor, self.project, "REVIEW_GET", "CUSTOMER_MEMBER")
        self.repository = Mock()
        self.repository.get_review.return_value = self.identity
        self.repository.get_round_subject_version.return_value = self.version
        self.repository.get_round.return_value = self.fixed
        self.subjects = Mock()
        self.subjects.authorize_read.side_effect = lambda tx, **k: AuthorizedReviewSubjectRead(**k)
        self.guard = Mock()

    def service(self, **overrides):
        return ReviewReadService(**(dict(unit_of_work=lambda: self.tx, sessions=self.sessions, projects=self.projects,
            license_guard=self.guard, repository=self.repository, subjects=self.subjects) | overrides))

    def denied(self, code, **overrides):
        with self.assertRaises(ReviewReadError) as exc:
            self.service(**overrides).get(self.query)
        self.assertEqual(exc.exception.code, code)

    def test_same_transaction_role_matrix_identity_and_fixed_version(self):
        for role in ALL_MEMBERS:
            self.projects.require_in_transaction.return_value = AuthorizedProjectAction(self.actor, self.project, "REVIEW_GET", role)
            result = self.service().get(self.query)
            self.assertIs(result.fixed_round, self.fixed)
            self.assertEqual(result.etag, '"v1"')
        for port in (self.sessions.authenticated_user, self.projects.require_in_transaction,
                     self.repository.get_review, self.repository.get_round_subject_version,
                     self.repository.get_round, self.subjects.authorize_read):
            self.assertTrue(all(call.args[0] is self.tx for call in port.call_args_list))
        versions = [call.kwargs["subject_version_id"] for call in self.subjects.authorize_read.call_args_list]
        self.assertEqual(versions, [None, self.version]*4)

    def test_identity_only_does_not_load_assignments_or_decisions(self):
        result = self.service().get(replace(self.query, round_id=None))
        self.assertIsNone(result.fixed_round)
        self.repository.get_round.assert_not_called()
        self.repository.get_round_subject_version.assert_not_called()

    def test_missing_owner_or_denied_identity_never_loads_round(self):
        self.denied("RESOURCE_NOT_FOUND", subjects=None)
        self.subjects.authorize_read.return_value = None
        self.subjects.authorize_read.side_effect = None
        self.denied("RESOURCE_NOT_FOUND")
        self.repository.get_round.assert_not_called()
        self.repository.get_round_subject_version.assert_not_called()

    def test_old_version_permission_is_separate_and_precedes_full_round_load(self):
        self.subjects.authorize_read.side_effect = lambda tx, **k: AuthorizedReviewSubjectRead(**k) if k["subject_version_id"] is None else None
        self.denied("RESOURCE_NOT_FOUND")
        self.repository.get_round.assert_not_called()

    def test_bad_subject_proofs_fail_closed(self):
        valid = AuthorizedReviewSubjectRead(self.actor, self.project, self.identity.subject_type, self.identity.subject_id, None)
        self.subjects.authorize_read.side_effect = None
        for proof in (True, SimpleNamespace(**vars(SimpleNamespace(user_id=self.actor))),
                      replace(valid, user_id=uuid4()), replace(valid, project_id=uuid4()),
                      replace(valid, subject_type="REQ-03"), replace(valid, subject_id=uuid4()),
                      replace(valid, subject_version_id=self.version)):
            self.subjects.authorize_read.return_value = proof
            self.denied("RESOURCE_NOT_FOUND")
        self.repository.get_round.assert_not_called()

    def test_bad_project_proof_or_project_error_stops_repository(self):
        valid = self.projects.require_in_transaction.return_value
        for proof in (None, replace(valid, user_id=uuid4()), replace(valid, project_id=uuid4()),
                      replace(valid, operation="PROJECT_GET"), replace(valid, project_role="DEPLOYMENT_ADMIN")):
            self.projects.require_in_transaction.return_value = proof
            self.denied("RESOURCE_NOT_FOUND")
        self.projects.require_in_transaction.side_effect = ProjectAuthorizationError("PROJECT_ARCHIVED")
        self.denied("RESOURCE_NOT_FOUND")
        self.repository.get_review.assert_not_called()

    def test_session_rejection_precedes_project_and_subject(self):
        for actor in (None, UUID(int=0), "user", True):
            self.sessions.authenticated_user.return_value = actor
            self.denied("AUTH_ACCESS_DENIED")
        self.projects.require_in_transaction.assert_not_called()

    def test_license_rejection_before_session(self):
        self.guard.require_valid.side_effect = RuntimeLicenseError("EXPIRED")
        self.denied("LICENSE_OPERATION_DENIED")
        self.sessions.authenticated_user.assert_not_called()

    def test_missing_identity_round_and_bad_scope_projection(self):
        self.repository.get_review.return_value = None
        self.denied("RESOURCE_NOT_FOUND")
        for view in (replace(self.identity, project_id=uuid4()),
                     replace(self.identity, scope="GLOBAL", project_id=None), replace(self.identity, review_id=uuid4()), True):
            self.repository.get_review.return_value = view
            self.denied("REVIEW_UNAVAILABLE")
        self.repository.get_review.return_value = self.identity
        self.repository.get_round_subject_version.return_value = None
        self.denied("RESOURCE_NOT_FOUND")

    def test_mismatched_fixed_version_or_round_projection_rejected(self):
        for value in (None, True, replace(self.fixed, subject_version_id=uuid4())):
            self.repository.get_round.return_value = value
            self.denied("REVIEW_UNAVAILABLE")

    def test_exception_and_bad_clock_do_not_leak_details(self):
        self.denied("REVIEW_UNAVAILABLE", clock=lambda: datetime.now())
        self.subjects.authorize_read.side_effect = RuntimeError("SQL private path must stay internal")
        self.denied("REVIEW_UNAVAILABLE")

    def test_request_validation_before_dependencies_and_token_repr_safe(self):
        for changes in (dict(session_token=b"x"), dict(project_id=None), dict(review_id=UUID(int=0)),
                        dict(trace_id=True), dict(round_id="id")):
            with self.assertRaises(ReviewReadError) as exc:
                self.service().get(replace(self.query, **changes))
            self.assertEqual(exc.exception.code, "VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
        self.assertNotIn("ssss", repr(self.query))
