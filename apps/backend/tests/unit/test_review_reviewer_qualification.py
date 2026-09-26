from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4
import unittest
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS, ProjectActorFacts
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService, ReviewReviewerEligibilityError
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess


class ReviewerQualificationTests(unittest.TestCase):
    def setUp(self):
        self.project, self.users, self.tx = uuid4(), (uuid4(), uuid4()), object()
        self.auth, self.projects = Mock(), Mock()
        self.auth.lock_enabled_users.side_effect = lambda tx, users: users
        self.projects.actor_facts.return_value = ProjectActorFacts("ACTIVE", "CUSTOMER_MEMBER")
        self.service = ProjectReviewerQualificationService(users=self.auth, projects=self.projects)

    def call(self, **changes):
        return self.service.qualify_in_transaction(self.tx, **(dict(project_id=self.project, reviewer_ids=self.users, allowed_roles=ALL_MEMBERS) | changes))

    def test_sorted_auth_first_and_original_assignment_order_preserved(self):
        calls = []
        self.auth.lock_enabled_users.side_effect = lambda tx, users: calls.append("auth") or users
        self.projects.actor_facts.side_effect = lambda tx, **k: calls.append("project") or ProjectActorFacts("ACTIVE", "CUSTOMER_MEMBER")
        result = self.call()
        self.assertEqual(tuple(v.user_id for v in result), self.users)
        self.assertEqual(calls, ["auth", "project", "project"])
        self.assertEqual(self.auth.lock_enabled_users.call_args.args, (self.tx, tuple(sorted(self.users))))
        self.assertTrue(all(c.kwargs["lock"] and c.args[0] is self.tx for c in self.projects.actor_facts.call_args_list))

    def test_empty_duplicate_unknown_role_and_invalid_scope_before_io(self):
        for changes in (dict(project_id=None), dict(project_id=UUID(int=0)), dict(reviewer_ids=()),
                        dict(reviewer_ids=self.users*2), dict(reviewer_ids=list(self.users)), dict(reviewer_ids=(True,)),
                        dict(allowed_roles=frozenset()), dict(allowed_roles={"CUSTOMER_MEMBER"}), dict(allowed_roles=frozenset({"DEPLOYMENT_ADMIN"}))):
            with self.subTest(changes=changes), self.assertRaises(ReviewReviewerEligibilityError): self.call(**changes)
        self.auth.lock_enabled_users.assert_not_called()

    def test_missing_or_malformed_enabled_ids_stops_project_checks(self):
        self.auth.lock_enabled_users.side_effect = None
        for result in ((), self.users[:1], list(sorted(self.users)), True):
            self.auth.lock_enabled_users.return_value = result
            with self.assertRaises(ReviewReviewerEligibilityError): self.call()
        self.projects.actor_facts.assert_not_called()

    def test_current_project_facts_and_role_policy_rejection(self):
        for facts in (None, True, ProjectActorFacts("ARCHIVED", "CUSTOMER_MEMBER"), ProjectActorFacts("ACTIVE", "PROJECT_MANAGER")):
            self.projects.actor_facts.return_value = facts
            with self.assertRaises(ReviewReviewerEligibilityError): self.call(allowed_roles=frozenset({"CUSTOMER_MEMBER"}))

    def test_auth_adapter_no_implicit_transaction_and_safe_error(self):
        with self.assertRaises(RuntimeError): SqlAlchemyReviewUserAccess().lock_enabled_users(SimpleNamespace(session=None), tuple(sorted(self.users)))
        self.assertEqual(str(ReviewReviewerEligibilityError()), "REVIEW_REVIEWER_INELIGIBLE")

    def test_prelock_observation_cannot_be_reused_in_other_tx_or_set(self):
        locked=self.service.lock_users_in_transaction(self.tx,reviewer_ids=self.users)
        with self.assertRaises(ReviewReviewerEligibilityError):
            self.service.qualify_locked_in_transaction(object(),project_id=self.project,locked=locked,allowed_roles=ALL_MEMBERS,reviewer_ids=self.users)
        with self.assertRaises(ReviewReviewerEligibilityError):
            self.service.qualify_locked_in_transaction(self.tx,project_id=self.project,locked=locked,allowed_roles=ALL_MEMBERS,reviewer_ids=(uuid4(),))
