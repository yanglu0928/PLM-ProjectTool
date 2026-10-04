from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.capability.application.change_state import (
    ArchiveCapabilityBaseline, CapabilityRestrictionMutation,
    CapabilityStateError, CapabilityStateService, PatchCapabilityBaseline,
    RestrictCapabilityVersion,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityVersionView,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
ACTOR = uuid.uuid4()
BASELINE = uuid.uuid4()
VERSION = uuid.uuid4()


def _baseline(state="ACTIVE", lock=4):
    return CapabilityBaselineView(
        BASELINE, "PLM.CORE", "Core", "Description", state,
        "sha256:" + "a" * 64, VERSION, NOW, NOW, f'"v{lock}"',
    )


def _version(state="APPROVED"):
    return CapabilityVersionView(
        VERSION, BASELINE, 1, state, "sha256:" + "a" * 64,
        "b" * 64, 1, 1, 1, None, uuid.uuid4(), uuid.uuid4(), NOW,
    )


class _Tx(AbstractContextManager):
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        type(self).commits += 1


class _Access:
    actor = ACTOR

    def authorized_admin(self, transaction, **kwargs):
        return self.actor


class _Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("TRUST_STATE_INVALID")
        return object()


class _Repo:
    baseline = _baseline()
    version = _version()
    error = None

    def _raise(self):
        if self.error:
            raise CapabilityStateError(self.error)

    def get_baseline(self, transaction, **kwargs):
        return self.baseline

    def patch(self, transaction, **kwargs):
        self._raise()
        self.patch_args = kwargs
        self.baseline = replace(
            self.baseline, name=kwargs["name"], description=kwargs["description"],
            etag='"v5"',
        )
        return self.baseline

    def archive(self, transaction, **kwargs):
        self._raise()
        self.archive_args = kwargs
        self.baseline = replace(self.baseline, state="ARCHIVED", etag='"v5"')
        return self.baseline

    def get_version(self, transaction, **kwargs):
        return self.version

    def restrict(self, transaction, **kwargs):
        self._raise()
        self.restrict_args = kwargs
        before = self.version.state
        self.version = replace(self.version, state="RESTRICTED")
        return CapabilityRestrictionMutation(self.version, before)


class _Receipts:
    replay = None
    completions = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        self.fingerprint = kwargs["request_fingerprint"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completions.append(kwargs["result"])


class _AuditRepo:
    events = []

    def append(self, transaction, event):
        self.events.append(event)
        return uuid.uuid4()


class CapabilityStateServiceTests(unittest.TestCase):
    def setUp(self):
        _Tx.commits = 0
        self.access = _Access()
        self.access.actor = ACTOR
        self.guard = _Guard()
        self.guard.denied = False
        self.repo = _Repo()
        self.repo.baseline = _baseline()
        self.repo.version = _version()
        self.repo.error = None
        self.receipts = _Receipts()
        self.receipts.replay = None
        self.receipts.completions = []
        self.audit_repo = _AuditRepo()
        self.audit_repo.events = []
        self.service = CapabilityStateService(
            unit_of_work=_Tx, access=self.access, license_guard=self.guard,
            repository=self.repo, receipts=self.receipts,
            audit=AuditService(self.audit_repo), clock=lambda: NOW,
        )
        self.patch = PatchCapabilityBaseline(
            b"s" * 32, b"c" * 32, uuid.uuid4(), BASELINE, 4,
            "Updated", "Updated description",
        )
        self.archive = ArchiveCapabilityBaseline(
            b"s" * 32, b"c" * 32, uuid.uuid4(), BASELINE, 4,
            str(uuid.uuid4()),
        )
        self.restrict = RestrictCapabilityVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), BASELINE, VERSION,
            "SOURCE_WITHDRAWN", str(uuid.uuid4()),
        )

    def test_patch_normalizes_and_audits(self):
        command = replace(self.patch, name="  Ｃｏｒｅ  ", description=None)
        result = self.service.patch(command)
        self.assertEqual("Core", result.name)
        self.assertIsNone(result.description)
        self.assertEqual("CAP_BASELINE_PATCHED", self.audit_repo.events[0].action)
        self.assertEqual(1, _Tx.commits)

    def test_archive_is_persistently_idempotent(self):
        first = self.service.archive(self.archive)
        self.assertEqual("ARCHIVED", first.state)
        self.assertEqual("CAP_BASELINE_ARCHIVED", self.audit_repo.events[0].action)
        self.assertEqual("V1_CAP_BASELINE_ARCHIVE", self.receipts.completions[0].ref_type)
        self.receipts.replay = IdempotencyResult(
            "V1_CAP_BASELINE_ARCHIVE", BASELINE, 200,
        )
        replay = self.service.archive(self.archive)
        self.assertEqual(first, replay)
        self.assertEqual(1, len(self.audit_repo.events))

    def test_restrict_preserves_reason_and_replays_without_second_audit(self):
        result = self.service.restrict(self.restrict)
        self.assertEqual("RESTRICTED", result.version.state)
        self.assertEqual("SOURCE_WITHDRAWN", result.reason_code)
        event = self.audit_repo.events[0]
        self.assertEqual(("APPROVED", "RESTRICTED"),
                         (event.before_state, event.after_state))
        self.receipts.replay = IdempotencyResult(
            "V1_CAP_VERSION_RESTRICT", VERSION, 200,
        )
        replay = self.service.restrict(self.restrict)
        self.assertEqual(result, replay)
        self.assertEqual(1, len(self.audit_repo.events))

    def test_admin_and_license_are_rechecked_fail_closed(self):
        self.access.actor = None
        with self.assertRaises(CapabilityStateError) as raised:
            self.service.patch(self.patch)
        self.assertEqual("AUTH_ACCESS_DENIED", raised.exception.code)
        self.access.actor = ACTOR
        self.guard.denied = True
        with self.assertRaises(CapabilityStateError) as raised:
            self.service.patch(self.patch)
        self.assertEqual("LICENSE_OPERATION_DENIED", raised.exception.code)

    def test_conflicts_are_preserved(self):
        for code, command, method in (
            ("CONFLICT_VERSION", self.patch, self.service.patch),
            ("CONFLICT_STATE", self.archive, self.service.archive),
            ("RESOURCE_NOT_FOUND", self.restrict, self.service.restrict),
        ):
            with self.subTest(code=code):
                self.repo.error = code
                with self.assertRaises(CapabilityStateError) as raised:
                    method(command)
                self.assertEqual(code, raised.exception.code)

    def test_untrusted_inputs_fail_before_io_and_tokens_are_redacted(self):
        invalid = (
            (self.patch, {"session_token": b"short"}, self.service.patch),
            (self.patch, {"expected_lock_version": -1}, self.service.patch),
            (self.patch, {"name": "\x00bad"}, self.service.patch),
            (self.archive, {"idempotency_key": "short"}, self.service.archive),
            (self.restrict, {"reason_code": "free text"}, self.service.restrict),
            (self.restrict, {"baseline_version_id": uuid.UUID(int=0)},
             self.service.restrict),
        )
        for command, changes, method in invalid:
            with self.subTest(changes=changes), self.assertRaises(
                    CapabilityStateError) as raised:
                method(replace(command, **changes))
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        self.assertNotIn("s" * 32, repr(self.archive))
        self.assertNotIn(self.archive.idempotency_key, repr(self.archive))


if __name__ == "__main__":
    unittest.main()
