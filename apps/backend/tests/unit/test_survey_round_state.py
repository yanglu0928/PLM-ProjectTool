from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.change_round import (
    CancelSurveyRound,
    CloseSurveyRound,
    OpenSurveyRound,
    PatchSurveyRound,
    SurveyRoundStateError,
    SurveyRoundStateService,
)
from plm_assistant.modules.survey.application.round_views import SurveyRoundView
from plm_assistant.modules.survey.application.round_completeness import (
    SurveyRoundCompletenessProof,
)


NOW = datetime(2026, 10, 6, 4, 0, tzinfo=timezone.utc)
ACTOR, PROJECT, SURVEY, VERSION, ROUND = (uuid.uuid4() for _ in range(5))


class Tx:
    commits = 0

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs): return ACTOR


class Guard:
    def require_valid(self, **kwargs): return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, kwargs["operation"],
            "IMPLEMENTATION_MEMBER" if kwargs["operation"] == "SURVEY_ROUND_PATCH"
            else "PROJECT_MANAGER",
        )


def view(state="PLANNED", version=0, **changed):
    base = SurveyRoundView(
        ROUND, SURVEY, VERSION, PROJECT, 1, state,
        NOW + timedelta(hours=1), NOW + timedelta(hours=2), "Customer site",
        ACTOR if state == "OPEN" else None, NOW if state == "OPEN" else None,
        None, None, None,
        cancelled_by=ACTOR if state == "CANCELLED" else None,
        cancelled_at=NOW if state == "CANCELLED" else None,
        cancellation_reason="Duplicate" if state == "CANCELLED" else None,
        created_by=ACTOR, created_at=NOW - timedelta(hours=1),
        updated_by=ACTOR, updated_at=NOW, etag=f'"v{version}"',
    )
    return replace(base, **changed)


class Repository:
    current = view()

    def get(self, transaction, **kwargs): return self.current

    def patch(self, transaction, **kwargs):
        self.current = view(
            version=kwargs["expected_lock_version"] + 1,
            scheduled_start_at=kwargs["scheduled_start_at"],
            scheduled_end_at=kwargs["scheduled_end_at"],
            location_note=kwargs["location_note"],
        )
        return self.current

    def open(self, transaction, **kwargs):
        self.current = view("OPEN", kwargs["expected_lock_version"] + 1)
        return self.current

    def cancel(self, transaction, **kwargs):
        self.current = view(
            "CANCELLED", kwargs["expected_lock_version"] + 1,
            cancellation_reason=kwargs["reason"],
        )
        return self.current

    def close(self, transaction, **kwargs):
        self.current = view(
            "CLOSED", kwargs["expected_lock_version"] + 1,
            opened_by=ACTOR, opened_at=NOW - timedelta(minutes=5),
            closed_by=ACTOR, closed_at=NOW,
            close_report_fingerprint=kwargs["report_fingerprint"],
        )
        return self.current


class Completeness:
    calls = []

    def prove(self, transaction, query):
        self.calls.append(query)
        return SurveyRoundCompletenessProof(
            ROUND, VERSION, PROJECT, 1, 1, 2, 2, 1, b"p" * 32,
        )


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


class SurveyRoundStateTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0
        Receipts.replay, Receipts.completed = None, []
        Audit.events = []
        self.repository, self.receipts = Repository(), Receipts()
        self.service = SurveyRoundStateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repository,
            receipts=self.receipts, audit=Audit(), clock=lambda: NOW,
        )
        common = (b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ROUND, 0)
        self.patch = PatchSurveyRound(
            *common, NOW + timedelta(hours=3), NOW + timedelta(hours=4),
            " Remote room ",
        )
        self.open = OpenSurveyRound(*common, str(uuid.uuid4()))
        self.cancel = CancelSurveyRound(*common, " Duplicate ", str(uuid.uuid4()))
        self.close = CloseSurveyRound(*common, str(uuid.uuid4()))

    def test_patch_normalizes_and_audits(self):
        result = self.service.patch(self.patch)
        self.assertEqual("Remote room", result.location_note)
        self.assertEqual('"v1"', result.etag)
        self.assertEqual("SURVEY_ROUND_PATCHED", Audit.events[0].action)
        self.assertEqual(1, Tx.commits)

    def test_open_is_receipted_and_replays_terminal_projection(self):
        result = self.service.open(self.open)
        self.assertEqual("OPEN", result.round_state)
        self.assertEqual("V1_SURVEY_ROUND_OPEN", self.receipts.scope.operation)
        self.assertEqual(
            IdempotencyResult("V1_SURVEY_ROUND_OPEN", ROUND, 200),
            Receipts.completed[0],
        )
        Tx.commits, Audit.events = 0, []
        Receipts.replay = Receipts.completed[0]
        replay = self.service.open(self.open)
        self.assertEqual(result, replay)
        self.assertEqual(1, Tx.commits)
        self.assertEqual([], Audit.events)

    def test_cancel_normalizes_reason_and_is_receipted(self):
        result = self.service.cancel(self.cancel)
        self.assertEqual("CANCELLED", result.round_state)
        self.assertEqual("Duplicate", result.cancellation_reason)
        self.assertEqual("SURVEY_ROUND_CANCELLED", Audit.events[0].action)
        self.assertEqual("USER_CANCELLED", Audit.events[0].reason_code)

    def test_close_is_explicitly_closed_until_completeness_owner_exists(self):
        with self.assertRaises(SurveyRoundStateError) as raised:
            self.service.close(self.close)
        self.assertEqual(
            "SURVEY_ROUND_COMPLETENESS_UNAVAILABLE", raised.exception.code,
        )
        self.assertEqual(0, Tx.commits)
        self.assertEqual([], Audit.events)
        self.assertEqual([], Receipts.completed)

    def test_close_proves_completeness_in_transaction_and_replays(self):
        Completeness.calls = []
        self.service = SurveyRoundStateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repository,
            receipts=self.receipts, audit=Audit(), completeness=Completeness(),
            clock=lambda: NOW,
        )
        result = self.service.close(self.close)
        self.assertEqual("CLOSED", result.round_state)
        self.assertEqual(b"p" * 32, result.close_report_fingerprint)
        self.assertEqual("PROJECT_MANAGER", Completeness.calls[0].actor_role)
        self.assertEqual("SURVEY_ROUND_CLOSED", Audit.events[0].action)
        self.assertEqual("OPEN", Audit.events[0].before_state)
        self.assertEqual("V1_SURVEY_ROUND_CLOSE", Receipts.completed[0].ref_type)
        Receipts.replay = Receipts.completed[0]
        replay = self.service.close(self.close)
        self.assertEqual(result, replay)
        self.assertEqual(1, len(Completeness.calls))

    def test_invalid_boundaries_and_secrets_fail_closed(self):
        invalid = (
            replace(self.patch, session_token=b"short"),
            replace(self.patch, scheduled_end_at=None),
            replace(self.patch, scheduled_end_at=NOW),
            replace(self.patch, location_note="\x00"),
            replace(self.open, expected_lock_version=-1),
            replace(self.open, idempotency_key="bad key"),
            replace(self.cancel, reason=""),
            replace(self.cancel, reason="\n"),
            replace(self.close, idempotency_key="bad key"),
        )
        for command in invalid:
            with self.subTest(command=type(command).__name__), self.assertRaises(
                    SurveyRoundStateError) as raised:
                method = (
                    self.service.patch if type(command) is PatchSurveyRound else
                    self.service.open if type(command) is OpenSurveyRound else
                    self.service.cancel if type(command) is CancelSurveyRound else
                    self.service.close
                )
                method(command)
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        for command in (self.patch, self.open, self.cancel, self.close):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            if hasattr(command, "idempotency_key"):
                self.assertNotIn(command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
