from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.handover.application.change_analysis import (
    ArchiveHandoverAnalysis, HandoverAnalysisStateError,
    HandoverAnalysisStateService, PatchHandoverAnalysis,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisView,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
ACTOR, PROJECT, ANALYSIS = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def view(state="ACTIVE", lock=4, purpose="Initial"):
    return HandoverAnalysisView(
        ANALYSIS, PROJECT, purpose, "sha256:" + "a" * 64, state, None,
        ACTOR, NOW, NOW, f'"v{lock}"',
    )


class Tx(AbstractContextManager):
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        type(self).commits += 1


class Access:
    actor = ACTOR

    def authenticated_user(self, transaction, **kwargs):
        return self.actor


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("TRUST_STATE_INVALID")
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        self.operation = kwargs["operation"]
        return SimpleNamespace(
            user_id=kwargs["user_id"], project_id=kwargs["project_id"],
            operation=kwargs["operation"],
        )


class Repo:
    current = view()
    error = None

    def _raise(self):
        if self.error:
            raise HandoverAnalysisStateError(self.error)

    def get(self, transaction, **kwargs):
        return self.current

    def patch(self, transaction, **kwargs):
        self._raise()
        self.args = kwargs
        self.current = replace(
            self.current, analysis_purpose=kwargs["analysis_purpose"],
            etag='"v5"',
        )
        return self.current

    def archive(self, transaction, **kwargs):
        self._raise()
        self.args = kwargs
        self.current = replace(self.current, analysis_state="ARCHIVED", etag='"v5"')
        return self.current


class Receipts:
    replay = None
    completions = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        self.fingerprint = kwargs["request_fingerprint"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completions.append(kwargs["result"])


class AuditRepo:
    events = []

    def append(self, transaction, event):
        self.events.append(event)
        return uuid.uuid4()


class HandoverAnalysisStateTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0
        self.access, self.guard = Access(), Guard()
        self.access.actor, self.guard.denied = ACTOR, False
        self.authorization = Authorization()
        self.repo = Repo()
        self.repo.current, self.repo.error = view(), None
        self.receipts = Receipts()
        self.receipts.replay, self.receipts.completions = None, []
        self.audit_repo = AuditRepo()
        self.audit_repo.events = []
        self.service = HandoverAnalysisStateService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=self.authorization, repository=self.repo,
            receipts=self.receipts, audit=AuditService(self.audit_repo),
            clock=lambda: NOW,
        )
        self.patch = PatchHandoverAnalysis(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ANALYSIS, 4,
            "Updated purpose",
        )
        self.archive = ArchiveHandoverAnalysis(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ANALYSIS, 4,
            str(uuid.uuid4()),
        )

    def test_patch_normalizes_and_audits(self):
        result = self.service.patch(replace(
            self.patch, analysis_purpose="  Ｔｅｃｈｎｉｃａｌ handover  ",
        ))
        self.assertEqual("Technical handover", result.analysis_purpose)
        self.assertEqual("HND_ANALYSIS_PATCH", self.authorization.operation)
        event = self.audit_repo.events[0]
        self.assertEqual("HND_ANALYSIS_PATCHED", event.action)
        self.assertEqual(("ACTIVE", "ACTIVE"),
                         (event.before_state, event.after_state))
        self.assertEqual(1, Tx.commits)

    def test_archive_is_persistently_idempotent(self):
        first = self.service.archive(self.archive)
        self.assertEqual("ARCHIVED", first.analysis_state)
        self.assertEqual("HND_ANALYSIS_ARCHIVED", self.audit_repo.events[0].action)
        self.assertEqual("V1_HND_ANALYSIS_ARCHIVE",
                         self.receipts.completions[0].ref_type)
        self.receipts.replay = IdempotencyResult(
            "V1_HND_ANALYSIS_ARCHIVE", ANALYSIS, 200,
        )
        replay = self.service.archive(self.archive)
        self.assertEqual(first, replay)
        self.assertEqual(1, len(self.audit_repo.events))

    def test_auth_license_and_repository_conflicts_fail_closed(self):
        self.access.actor = None
        with self.assertRaises(HandoverAnalysisStateError) as caught:
            self.service.patch(self.patch)
        self.assertEqual("AUTH_ACCESS_DENIED", caught.exception.code)
        self.access.actor = ACTOR
        self.guard.denied = True
        with self.assertRaises(HandoverAnalysisStateError) as caught:
            self.service.patch(self.patch)
        self.assertEqual("LICENSE_OPERATION_DENIED", caught.exception.code)
        self.guard.denied = False
        for code, command, method in (
            ("CONFLICT_VERSION", self.patch, self.service.patch),
            ("HANDOVER_STATE_CONFLICT", self.archive, self.service.archive),
            ("RESOURCE_NOT_FOUND", self.patch, self.service.patch),
        ):
            with self.subTest(code=code):
                self.repo.error = code
                with self.assertRaises(HandoverAnalysisStateError) as caught:
                    method(command)
                self.assertEqual(code, caught.exception.code)

    def test_untrusted_input_fails_before_io_and_repr_redacts_secrets(self):
        invalid = (
            (self.patch, {"session_token": b"short"}, self.service.patch),
            (self.patch, {"expected_lock_version": -1}, self.service.patch),
            (self.patch, {"analysis_purpose": "bad\x00"}, self.service.patch),
            (self.archive, {"idempotency_key": "short"}, self.service.archive),
            (self.archive, {"handover_analysis_id": uuid.UUID(int=0)},
             self.service.archive),
        )
        for command, changes, method in invalid:
            with self.subTest(changes=changes), self.assertRaises(
                    HandoverAnalysisStateError) as caught:
                method(replace(command, **changes))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)
        self.assertNotIn("s" * 32, repr(self.archive))
        self.assertNotIn(self.archive.idempotency_key, repr(self.archive))


if __name__ == "__main__":
    unittest.main()
