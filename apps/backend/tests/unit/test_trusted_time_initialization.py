from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.trusted_time_initialization import (
    InitializeTrustedTime, TrustedTimeInitializationError,
    TrustedTimeInitializationService,
)


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


class Transaction:
    def __init__(self, dependencies):
        self.dependencies, self.committed = dependencies, False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.committed:
            self.dependencies.created += 1

    def commit(self):
        self.committed = True


class Dependencies:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.state_id = uuid.uuid4()
        self.created = 0
        self.audit_broken = False
        self.reads = 0

    def uow(self):
        return Transaction(self)

    def authorized_admin(self, tx, **kwargs):
        assert kwargs["now"] == NOW
        return self.actor

    def create_pristine(self, tx):
        self.reads += 1
        return self.state_id

    def append(self, tx, event):
        if self.audit_broken:
            raise RuntimeError("audit unavailable")
        assert event.action == "LICENSE_TRUSTED_TIME_INITIALIZED"
        assert event.actor_id == self.actor
        assert event.target_object_id == self.state_id


class TrustedTimeInitializationTests(unittest.TestCase):
    def setUp(self):
        self.deps = Dependencies()
        self.service = TrustedTimeInitializationService(
            unit_of_work=self.deps.uow, access=self.deps, repository=self.deps,
            audit=self.deps, clock=lambda: NOW,
        )
        self.command = InitializeTrustedTime(b"s" * 32, b"c" * 32, uuid.uuid4())

    def test_first_initialization(self):
        self.assertEqual(self.service.initialize_once(self.command), self.deps.state_id)
        self.assertEqual(self.deps.created, 1)

    def test_denied_admin_cannot_create(self):
        self.deps.actor = None
        with self.assertRaises(TrustedTimeInitializationError) as caught:
            self.service.initialize_once(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.deps.reads, 0)

    def test_existing_or_damaged_state_is_not_replaced(self):
        self.deps.state_id = None
        with self.assertRaises(TrustedTimeInitializationError) as caught:
            self.service.initialize_once(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_CONFLICT")
        self.assertEqual(self.deps.created, 0)

    def test_audit_failure_rolls_back(self):
        self.deps.audit_broken = True
        with self.assertRaises(TrustedTimeInitializationError) as caught:
            self.service.initialize_once(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.deps.created, 0)

    def test_invalid_command_is_rejected_early(self):
        with self.assertRaises(TrustedTimeInitializationError) as caught:
            self.service.initialize_once(InitializeTrustedTime(b"short", b"c" * 32, uuid.uuid4()))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.deps.reads, 0)

    def test_invalid_clock_fails_closed(self):
        self.service._clock = lambda: NOW.replace(tzinfo=None)
        with self.assertRaises(TrustedTimeInitializationError) as caught:
            self.service.initialize_once(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.deps.reads, 0)


if __name__ == "__main__":
    unittest.main()
