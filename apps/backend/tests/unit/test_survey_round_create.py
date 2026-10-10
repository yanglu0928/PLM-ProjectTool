from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.create_round import (
    CreateSurveyRound,
    SurveyRoundCreateError,
    SurveyRoundCreateService,
)
from plm_assistant.modules.survey.application.round_views import SurveyRoundView


NOW = datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc)
ACTOR, PROJECT, SURVEY, VERSION, ROUND = (uuid.uuid4() for _ in range(5))


class Tx:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs):
        return ACTOR


class Guard:
    def require_valid(self, **kwargs):
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, "SURVEY_ROUND_CREATE", "IMPLEMENTATION_MEMBER",
        )


def view(round_id=ROUND):
    return SurveyRoundView(
        round_id, SURVEY, VERSION, PROJECT, 1, "PLANNED",
        NOW + timedelta(hours=1), NOW + timedelta(hours=2), "Customer site",
        None, None, None, None, None,
        created_by=ACTOR, created_at=NOW, updated_at=NOW,
    )


class Repository:
    def create(self, transaction, **kwargs):
        self.created = kwargs
        return view(kwargs["survey_round_id"])

    def get_initial(self, transaction, **kwargs):
        return view(kwargs["survey_round_id"])


class Receipts:
    replay = None
    completed = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completed.append(kwargs["result"])


class Audit:
    events = []

    def append(self, transaction, event):
        self.events.append(event)
        return uuid.uuid4()


class SurveyRoundCreateTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0
        Receipts.replay, Receipts.completed = None, []
        Audit.events = []
        self.repository, self.receipts = Repository(), Receipts()
        self.service = SurveyRoundCreateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repository,
            receipts=self.receipts, audit=Audit(), clock=lambda: NOW,
        )
        self.command = CreateSurveyRound(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, SURVEY, VERSION,
            NOW + timedelta(hours=1), NOW + timedelta(hours=2),
            "Customer site", str(uuid.uuid4()),
        )

    def test_create_is_atomic_audited_and_receipted(self):
        result = self.service.create(self.command)
        self.assertEqual("PLANNED", result.round_state)
        self.assertEqual(1, Tx.commits)
        self.assertEqual("V1_SURVEY_ROUND_CREATE", self.receipts.scope.operation)
        self.assertEqual("SURVEY_ROUND_CREATED", Audit.events[0].action)
        self.assertEqual(
            IdempotencyResult("V1_SURVEY_ROUND_CREATE", result.survey_round_id, 201),
            Receipts.completed[0],
        )

    def test_replay_reads_original_without_commit_or_new_audit(self):
        Receipts.replay = IdempotencyResult("V1_SURVEY_ROUND_CREATE", ROUND, 201)
        result = self.service.create(self.command)
        self.assertEqual(ROUND, result.survey_round_id)
        self.assertEqual(0, Tx.commits)
        self.assertEqual([], Audit.events)

    def test_invalid_schedule_location_identity_and_secret_are_closed(self):
        for changed in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"survey_version_id": uuid.UUID(int=0)},
            {"scheduled_end_at": None},
            {"scheduled_end_at": NOW},
            {"location_note": " padded "}, {"location_note": ""},
        ):
            with self.subTest(changed=changed), self.assertRaises(
                    SurveyRoundCreateError) as raised:
                self.service.create(replace(self.command, **changed))
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
