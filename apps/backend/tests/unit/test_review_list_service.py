from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import UUID, uuid4

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS,
    AuthorizedProjectAction,
    ProjectAuthorizationError,
)
from plm_assistant.modules.review.application.list_contract import (
    MyReviewAssignmentSummary,
    ReviewListActiveRoundSummary,
    ReviewListItem,
    ReviewListQuery,
)
from plm_assistant.modules.review.application.list_service import (
    ReviewListError,
    ReviewListService,
)
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ReviewListServiceTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid4(), uuid4()
        self.now = datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc)
        self.query = ReviewListQuery(
            b"s" * 32, uuid4(), self.project, page_size=2,
        )
        self.tx = Tx()
        self.sessions = Mock()
        self.sessions.authenticated_user.return_value = self.actor
        self.projects = Mock()
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(
            self.actor, self.project, "REVIEW_LIST", "PROJECT_MANAGER",
        )
        self.guard = Mock()
        self.repository = Mock()
        self.subjects = Mock()
        self.subjects.authorize_read.side_effect = (
            lambda tx, **values: AuthorizedReviewSubjectRead(**values)
        )

    def item(
        self, age: int, *, pending: bool = True, project_id=None,
        subject_id=None, terminal: bool = False,
    ) -> ReviewListItem:
        subject_id = subject_id or uuid4()
        assignment = MyReviewAssignmentSummary(
            uuid4(), "PENDING" if pending else "DECIDED",
            None if pending else "APPROVE",
            None if pending else self.now - timedelta(seconds=age),
        )
        active = None if terminal else ReviewListActiveRoundSummary(
            uuid4(), 1, uuid4(), self.now - timedelta(seconds=age), assignment,
        )
        return ReviewListItem(
            uuid4(), project_id or self.project, "HND-02", subject_id,
            "CUSTOMER_ALL_V1", "APPROVED" if terminal else "IN_REVIEW",
            uuid4(), self.now - timedelta(seconds=age),
            '"v2"' if terminal else '"v1"', active,
        )

    def service(self, **overrides):
        dependencies = dict(
            unit_of_work=lambda: self.tx,
            sessions=self.sessions,
            projects=self.projects,
            license_guard=self.guard,
            repository=self.repository,
            subjects=self.subjects,
            clock=lambda: self.now,
        )
        return ReviewListService(**(dependencies | overrides))

    def denied(self, code, query=None, **overrides):
        with self.assertRaises(ReviewListError) as caught:
            self.service(**overrides).list(query or self.query)
        self.assertEqual(caught.exception.code, code)

    def test_all_roles_hidden_candidate_short_page_and_raw_cursor(self):
        hidden_id = uuid4()
        hidden = self.item(1, subject_id=hidden_id)
        visible = self.item(2)
        extra = self.item(3)
        self.repository.list_candidates.return_value = (hidden, visible, extra)
        self.subjects.authorize_read.side_effect = lambda tx, **values: (
            None if values["subject_id"] == hidden_id
            else AuthorizedReviewSubjectRead(**values)
        )
        for role in ALL_MEMBERS:
            with self.subTest(role=role):
                self.projects.require_in_transaction.return_value = (
                    AuthorizedProjectAction(
                        self.actor, self.project, "REVIEW_LIST", role,
                    )
                )
                self.subjects.reset_mock()
                page = self.service().list(self.query)
                self.assertEqual(page.items, (visible,))
                self.assertTrue(page.has_more)
                self.assertEqual(page.next_position, visible.position)
                calls = self.subjects.authorize_read.call_args_list
                self.assertEqual(
                    [call.kwargs["subject_id"] for call in calls],
                    [hidden.subject_id, visible.subject_id, visible.subject_id],
                )
                self.assertNotIn(extra.subject_id, {
                    call.kwargs["subject_id"] for call in calls
                })
        self.assertTrue(all(
            call.args[0] is self.tx
            for port in (
                self.sessions.authenticated_user,
                self.projects.require_in_transaction,
                self.repository.list_candidates,
                self.subjects.authorize_read,
            )
            for call in port.call_args_list
        ))
        self.assertEqual(self.guard.require_valid.call_count, len(ALL_MEMBERS) * 2)

    def test_empty_hidden_page_can_continue_and_terminal_needs_identity_only(self):
        one, two, extra = self.item(1), self.item(2), self.item(3, terminal=True)
        self.repository.list_candidates.return_value = (one, two, extra)
        self.subjects.authorize_read.return_value = None
        self.subjects.authorize_read.side_effect = None
        page = self.service().list(self.query)
        self.assertEqual(page.items, ())
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_position, two.position)

        self.repository.list_candidates.return_value = (extra,)
        self.subjects.authorize_read.side_effect = (
            lambda tx, **values: AuthorizedReviewSubjectRead(**values)
        )
        self.subjects.reset_mock()
        page = self.service().list(replace(
            self.query, before=two.position,
        ))
        self.assertEqual(page.items, (extra,))
        self.assertFalse(page.has_more)
        self.assertIsNone(page.next_position)
        self.assertEqual(len(self.subjects.authorize_read.call_args_list), 1)
        self.assertIsNone(
            self.subjects.authorize_read.call_args.kwargs["subject_version_id"]
        )

    def test_my_pending_contract_and_repository_arguments(self):
        item = self.item(1)
        query = replace(self.query, view="my_pending", page_size=1)
        self.repository.list_candidates.return_value = (item,)
        page = self.service().list(query)
        self.assertEqual(page.items, (item,))
        self.repository.list_candidates.assert_called_once_with(
            self.tx,
            project_id=self.project,
            actor_id=self.actor,
            view="my_pending",
            before=None,
            limit=2,
        )

        self.repository.list_candidates.return_value = (self.item(2, pending=False),)
        self.denied("REVIEW_UNAVAILABLE", query)
        self.repository.list_candidates.return_value = (self.item(2, terminal=True),)
        self.denied("REVIEW_UNAVAILABLE", query)

    def test_candidate_corruption_fails_closed_before_subject_authorization(self):
        newer, older = self.item(1), self.item(2)
        invalid_sets = (
            (older, newer),
            (newer, newer),
            (replace(newer, project_id=uuid4()),),
            (newer, older, self.item(3), self.item(4)),
            [newer],
            (True,),
        )
        for candidates in invalid_sets:
            with self.subTest(candidates=type(candidates).__name__):
                self.repository.list_candidates.return_value = candidates
                self.subjects.reset_mock()
                self.denied("REVIEW_UNAVAILABLE")
                self.subjects.authorize_read.assert_not_called()

    def test_auth_license_owner_and_internal_failures_are_distinct(self):
        item = self.item(1)
        self.repository.list_candidates.return_value = (item,)

        self.guard.require_valid.side_effect = RuntimeLicenseError("EXPIRED")
        self.denied("LICENSE_OPERATION_DENIED")
        self.sessions.authenticated_user.assert_not_called()
        self.guard.require_valid.side_effect = None

        for actor in (None, UUID(int=0), True):
            self.sessions.authenticated_user.return_value = actor
            self.denied("AUTH_ACCESS_DENIED")
        self.sessions.authenticated_user.return_value = self.actor

        self.projects.require_in_transaction.side_effect = ProjectAuthorizationError(
            "RESOURCE_NOT_FOUND"
        )
        self.denied("RESOURCE_NOT_FOUND")
        self.repository.list_candidates.assert_not_called()
        self.projects.require_in_transaction.side_effect = None
        valid = AuthorizedProjectAction(
            self.actor, self.project, "REVIEW_LIST", "PROJECT_MANAGER",
        )
        for proof in (
            None,
            replace(valid, operation="REVIEW_GET"),
            replace(valid, user_id=uuid4()),
            replace(valid, project_id=uuid4()),
            replace(valid, project_role="DEPLOYMENT_ADMIN"),
        ):
            self.projects.require_in_transaction.return_value = proof
            self.denied("RESOURCE_NOT_FOUND")
        self.projects.require_in_transaction.return_value = valid

        self.subjects.authorize_read.side_effect = RuntimeError(
            "private owner detail"
        )
        self.denied("REVIEW_UNAVAILABLE")
        self.subjects.authorize_read.side_effect = None
        self.subjects.authorize_read.return_value = SimpleNamespace(
            user_id=self.actor
        )
        page = self.service().list(self.query)
        self.assertEqual(page.items, ())

    def test_revalidates_license_and_validates_request_before_dependencies(self):
        self.repository.list_candidates.return_value = (self.item(1),)
        self.guard.require_valid.side_effect = [None, RuntimeLicenseError("EXPIRED")]
        self.denied("LICENSE_OPERATION_DENIED")

        self.guard.reset_mock()
        self.guard.require_valid.side_effect = None
        for query in (None, True, object()):
            with self.subTest(query=type(query).__name__):
                with self.assertRaises(ReviewListError) as caught:
                    self.service().list(query)
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
        self.denied("REVIEW_UNAVAILABLE", clock=lambda: datetime.now())

    def test_constructor_requires_every_dependency(self):
        values = dict(
            unit_of_work=lambda: self.tx,
            sessions=self.sessions,
            projects=self.projects,
            license_guard=self.guard,
            repository=self.repository,
            subjects=self.subjects,
        )
        for key in values:
            with self.subTest(key=key), self.assertRaises(ValueError):
                ReviewListService(**(values | {key: None}))
