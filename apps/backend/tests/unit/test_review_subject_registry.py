from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectRegistry,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)


class Owner:
    def __init__(self, subject_type: str) -> None:
        self.SUBJECT_TYPE = subject_type
        for method in (
            "authorize_create", "authorize_replay",
            "prepare_start_in_transaction", "finalize_start_in_transaction",
            "assert_active_lock_in_transaction",
            "require_start_replay_access_in_transaction",
            "require_transition_access_in_transaction",
            "assert_transition_lock_in_transaction",
            "consume_terminal_in_transaction",
            "assert_terminal_consumed_in_transaction",
            "require_transition_replay_access_in_transaction",
        ):
            setattr(self, method, Mock(name=f"{subject_type}.{method}"))


class ProjectReviewSubjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.handover, self.survey = Owner("HND-02"), Owner("SRV-02")
        self.registry = ProjectReviewSubjectRegistry(
            (self.handover, self.survey),
        )

    def test_creation_and_replay_dispatch_by_subject_type(self):
        self.survey.authorize_create.return_value = "survey-proof"
        result = self.registry.authorize_create(
            "tx", user_id="user", project_id="project",
            subject_type="SRV-02", subject_id="survey",
            subject_version_id="version",
        )
        self.assertEqual("survey-proof", result)
        self.survey.authorize_create.assert_called_once()
        self.handover.authorize_create.assert_not_called()

        review = SimpleNamespace(subject_type="HND-02")
        self.handover.authorize_replay.return_value = True
        self.assertTrue(self.registry.authorize_replay(
            "tx", user_id="user", review=review,
        ))
        self.handover.authorize_replay.assert_called_once_with(
            "tx", user_id="user", review=review,
        )

    def test_start_transition_and_replays_dispatch_consistently(self):
        review = SimpleNamespace(subject_type="SRV-02")
        request = SimpleNamespace(review=review)
        transition = SimpleNamespace(before=SimpleNamespace(review=review))

        self.registry.prepare_start_in_transaction("tx", request)
        self.registry.finalize_start_in_transaction("tx", request)
        self.registry.assert_active_lock_in_transaction("tx", request)
        self.registry.require_start_replay_access_in_transaction(
            "tx", actor_id="actor", review=review, round_ref="round",
        )
        self.registry.require_transition_access_in_transaction("tx", transition)
        self.registry.assert_transition_lock_in_transaction("tx", transition)
        self.registry.consume_terminal_in_transaction("tx", transition)
        self.registry.assert_terminal_consumed_in_transaction("tx", transition)
        self.registry.require_transition_replay_access_in_transaction(
            "tx", actor_id="actor", review=review, result="result",
        )

        for method in (
            "prepare_start_in_transaction", "finalize_start_in_transaction",
            "assert_active_lock_in_transaction",
            "require_start_replay_access_in_transaction",
            "require_transition_access_in_transaction",
            "assert_transition_lock_in_transaction",
            "consume_terminal_in_transaction",
            "assert_terminal_consumed_in_transaction",
            "require_transition_replay_access_in_transaction",
        ):
            getattr(self.survey, method).assert_called_once()
            getattr(self.handover, method).assert_not_called()

    def test_unknown_subject_fails_closed_for_every_callback_family(self):
        review = SimpleNamespace(subject_type="UNKNOWN")
        self.assertIsNone(self.registry.authorize_create(
            "tx", user_id="user", project_id="project",
            subject_type="UNKNOWN", subject_id="subject",
            subject_version_id="version",
        ))
        self.assertFalse(self.registry.authorize_replay(
            "tx", user_id="user", review=review,
        ))
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.registry.prepare_start_in_transaction(
                "tx", SimpleNamespace(review=review),
            )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.registry.require_transition_access_in_transaction(
                "tx", SimpleNamespace(before=SimpleNamespace(review=review)),
            )

    def test_empty_duplicate_or_incomplete_registry_is_rejected(self):
        with self.assertRaises(ValueError):
            ProjectReviewSubjectRegistry(())
        with self.assertRaises(ValueError):
            ProjectReviewSubjectRegistry((self.survey, Owner("SRV-02")))
        with self.assertRaises(ValueError):
            ProjectReviewSubjectRegistry((Owner("bad"),))
        with self.assertRaises(ValueError):
            ProjectReviewSubjectRegistry((SimpleNamespace(SUBJECT_TYPE="BAD"),))


if __name__ == "__main__":
    unittest.main()
