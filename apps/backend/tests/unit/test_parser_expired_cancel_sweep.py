from __future__ import annotations

import unittest
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone

from plm_assistant.modules.jobs.application.parse_cancel_scan import (
    ExpiredParserCancelCandidate, ExpiredParserCancelCursor,
    ExpiredParserCancelCandidates,
)
from plm_assistant.modules.parser.application.cancel_attempt import ParserCancellationError
from plm_assistant.modules.parser.application.sweep_expired_cancel import ParserExpiredCancelSweep


class _Actor:
    def __init__(self):
        self.value = uuid.uuid4()

    def assert_current(self):
        return self.value


class _Scan:
    def __init__(self, candidate):
        self.candidate = candidate
        self.calls = []

    def scan_next(self, tx, *, after=None):
        self.calls.append(after)
        value, self.candidate = self.candidate, None
        return value


class _Recovery:
    def __init__(self, actor):
        self._system_actor = actor
        self.calls = 0

    def recover(self, *, command):
        self.calls += 1
        raise ParserCancellationError("STALE_LEASE")

    def verify_committed(self, *, command):
        raise ParserCancellationError()


class ParserExpiredCancelSweepTests(unittest.TestCase):
    def setUp(self):
        self.actor = _Actor()
        self.candidate = ExpiredParserCancelCandidate(
            ExpiredParserCancelCursor(datetime.now(timezone.utc), uuid.uuid4()),
            1, "parser-test")
        self.scan = _Scan(self.candidate)
        self.recovery = _Recovery(self.actor)
        self.sweep = ParserExpiredCancelSweep(unit_of_work=lambda: nullcontext(object()),
            candidates=ExpiredParserCancelCandidates(repository=self.scan),
            recovery=self.recovery, system_actor=self.actor)

    def test_race_with_old_generation_is_superseded_and_cursor_advances(self):
        outcome = self.sweep.run_next()
        self.assertEqual((outcome.kind, outcome.job_id),
                         ("SUPERSEDED", self.candidate.cursor.job_id))
        self.assertEqual(self.sweep.run_next().kind, "IDLE")
        self.assertEqual(self.scan.calls, [None, self.candidate.cursor])
        self.assertEqual(self.recovery.calls, 1)

    def test_changed_identity_during_scan_cannot_dispatch(self):
        original_scan = self.scan.scan_next

        def changed(tx, *, after=None):
            result = original_scan(tx, after=after)
            self.actor.value = uuid.uuid4()
            return result

        self.scan.scan_next = changed
        with self.assertRaises(ParserCancellationError) as raised:
            self.sweep.run_next()
        self.assertEqual(raised.exception.code, "SYSTEM_ACTOR_UNAVAILABLE")
        self.assertEqual(self.recovery.calls, 0)

    def test_wrong_identity_dependency_rejected(self):
        with self.assertRaises(ValueError):
            ParserExpiredCancelSweep(unit_of_work=lambda: nullcontext(object()),
                candidates=ExpiredParserCancelCandidates(repository=self.scan),
                recovery=self.recovery, system_actor=_Actor())


if __name__ == "__main__":
    unittest.main()
