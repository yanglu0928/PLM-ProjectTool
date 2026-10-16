from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.solution.application.reference_source_qualification import (
    QualifiedReferenceSources, VerifiedReferenceDocument,
)
from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationError, GlobalReferencePublicationResult,
    GlobalReferencePublicationService, LockedGlobalPublicationTarget,
    SetGlobalReferencePublication,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    LockedReferenceEligibility,
)


class GlobalReferencePublicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor, self.root, self.version, self.document, self.confirmation = (
            uuid.uuid4() for _ in range(5))
        self.now = datetime.now(timezone.utc)
        self.reference = LockedReferenceEligibility(
            self.root, self.version, "GLOBAL", None, "ELIGIBLE", 1,
            "PLM", "DEIDENTIFIED", {}, (self.document,), (), b"a" * 32,
            self.confirmation,
        )
        self.target = LockedGlobalPublicationTarget(
            self.reference, True, 0, None, None)
        self.command = SetGlobalReferencePublication(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.root, self.version,
            0, "PUBLISH", "审定展示标签", "审定无客户信息", "unit-publish-key-01")
        self.view = GlobalReferencePublicationResult(
            uuid.uuid4(), self.root, self.version, 1, "PUBLISH",
            "审定展示标签", "审定无客户信息", self.now)
        self.tx = MagicMock()
        self.uow = Mock()
        self.uow.return_value = MagicMock()
        self.uow.return_value.__enter__ = Mock(return_value=self.tx)
        self.uow.return_value.__exit__ = Mock(return_value=False)
        self.admin, self.guard = Mock(), Mock()
        self.admin.authorized_admin.return_value = self.actor
        self.source, self.repo, self.receipts, self.audit = (
            Mock() for _ in range(4))
        self.source.qualify.return_value = QualifiedReferenceSources(
            "GLOBAL", None, (VerifiedReferenceDocument(
                uuid.uuid4(), self.document, "GLOBAL", None,
                "REFERENCE_MATERIAL", b"d" * 32),), (), b"a" * 32,
            self.confirmation)
        self.repo.current.return_value = self.target
        self.repo.append.side_effect = lambda tx, *, current, event_id, actor_id, command: (
            GlobalReferencePublicationResult(
                event_id, self.root, self.version, current.latest_event_no + 1,
                command.event_kind, command.display_label, command.reason, self.now))
        self.receipts.reserve.return_value = None
        self.service = GlobalReferencePublicationService(
            unit_of_work=self.uow, admin=self.admin,
            license_guard=self.guard, sources=self.source,
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: self.now)

    def test_publish_requires_current_sources_and_writes_once(self) -> None:
        self.assertEqual(self.service.set(self.command).event_kind, "PUBLISH")
        self.source.qualify.assert_called_once()
        self.repo.append.assert_called_once()
        self.audit.append.assert_called_once()
        self.receipts.complete.assert_called_once()
        self.tx.commit.assert_called_once()

    def test_same_key_returns_original_without_second_audit(self) -> None:
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_SOL_GLOBAL_REFERENCE_PUBLICATION_SET",
            self.view.publication_event_id, 200)
        self.repo.result.return_value = self.view
        self.assertEqual(self.service.set(self.command), self.view)
        self.repo.current.assert_not_called()
        self.repo.append.assert_not_called()
        self.audit.append.assert_not_called()

    def test_stale_version_event_and_eligibility_fail_closed(self) -> None:
        for target, expected in (
            (LockedGlobalPublicationTarget(
                self.reference, True, 1, "REVOKE", self.version),
             "VERSION_CONFLICT"),
            (LockedGlobalPublicationTarget(
                self.reference, False, 0, None, None), "CONFLICT_STATE"),
        ):
            with self.subTest(expected=expected):
                self.repo.current.return_value = target
                with self.assertRaises(GlobalReferencePublicationError) as caught:
                    self.service.set(self.command)
                self.assertEqual(caught.exception.code, expected)
        self.repo.append.assert_not_called()

    def test_changed_source_or_confirmation_rejected(self) -> None:
        for proof in (
            QualifiedReferenceSources("GLOBAL", None, (), (), b"x" * 32,
                                      self.confirmation),
            QualifiedReferenceSources("GLOBAL", None, (), (), b"a" * 32,
                                      uuid.uuid4()),
        ):
            with self.subTest(proof=proof.content_fingerprint):
                self.source.qualify.return_value = proof
                with self.assertRaises(GlobalReferencePublicationError) as caught:
                    self.service.set(self.command)
                self.assertEqual(caught.exception.code, "CONFLICT_STATE")
        self.repo.append.assert_not_called()

    def test_revoke_allows_expired_source_but_requires_latest_publish(self) -> None:
        command = SetGlobalReferencePublication(
            self.command.session_token, self.command.csrf_token,
            self.command.trace_id, self.root, self.version, 1,
            "REVOKE", None, "管理员撤回", "unit-revoke-key-01")
        target = LockedGlobalPublicationTarget(
            LockedReferenceEligibility(
                self.root, self.version, "GLOBAL", None, "RESTRICTED", 2,
                "PLM", "DEIDENTIFIED", {}, (self.document,), (), b"a" * 32,
                self.confirmation),
            False, 1, "PUBLISH", self.version)
        self.repo.current.return_value = target
        self.assertEqual(self.service.set(command).event_kind, "REVOKE")
        self.source.qualify.assert_not_called()
        self.repo.current.return_value = LockedGlobalPublicationTarget(
            target.reference, False, 1, "REVOKE", self.version)
        with self.assertRaises(GlobalReferencePublicationError) as caught:
            self.service.set(command)
        self.assertEqual(caught.exception.code, "CONFLICT_STATE")

    def test_non_admin_and_invalid_label_rejected(self) -> None:
        self.admin.authorized_admin.return_value = None
        with self.assertRaises(GlobalReferencePublicationError) as caught:
            self.service.set(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        for label in (" raw ", "line\nbreak", "e\u0301", ""):
            bad = SetGlobalReferencePublication(
                self.command.session_token, self.command.csrf_token,
                self.command.trace_id, self.root, self.version, 0,
                "PUBLISH", label, "审定", "unit-bad-key-0001")
            with self.assertRaises(GlobalReferencePublicationError) as caught:
                self.service.set(bad)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_license_denial_prevents_publication(self) -> None:
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_EXPIRED")
        with self.assertRaises(GlobalReferencePublicationError) as caught:
            self.service.set(self.command)
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.repo.current.assert_not_called()
        self.repo.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
