from __future__ import annotations

import hashlib
import unittest
import uuid

from plm_assistant.modules.audit.application.public import (
    AuditEventDraft,
    AuditEventValidationError,
    AuditService,
)
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    AuditTransactionError,
    SqlAlchemyAuditRepository,
)


TRACE_ID, ACTOR_ID, PROJECT_ID, OBJECT_ID = (uuid.uuid4() for _ in range(4))


def draft(**changes: object) -> AuditEventDraft:
    fields = dict(
        trace_id=TRACE_ID, event_scope="PROJECT", target_project_id=PROJECT_ID,
        actor_type="USER", actor_id=ACTOR_ID, original_actor_id=None,
        actor_hint_digest=None, action="DOCUMENT_CREATE", outcome="SUCCESS",
        target_owner_module="document", target_object_type="DOC-01",
        target_object_id=OBJECT_ID, before_state=None, after_state="DRAFT",
    )
    fields.update(changes)
    return AuditEventDraft(**fields)


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, AuditEventDraft]] = []

    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        self.calls.append((transaction, event))
        return OBJECT_ID


class AuditServiceTests(unittest.TestCase):
    def test_passes_same_transaction_to_repository_without_committing(self) -> None:
        repository = Recorder()
        transaction = object()
        event = draft()
        self.assertEqual(AuditService(repository).append(transaction, event), OBJECT_ID)
        self.assertEqual(repository.calls, [(transaction, event)])

    def test_missing_dependencies_and_transaction_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            AuditService(None)
        with self.assertRaises(ValueError):
            AuditService(Recorder()).append(None, draft())
        with self.assertRaises(TypeError):
            AuditService(Recorder()).append(object(), object())
        with self.assertRaises(AuditTransactionError):
            SqlAlchemyAuditRepository().append(object(), draft())

    def test_scope_and_actor_shapes(self) -> None:
        for changes in (
            {"event_scope": "PROJECT", "target_project_id": None},
            {"event_scope": "DEPLOYMENT"},
            {"actor_type": "SYSTEM", "original_actor_id": None},
            {"actor_type": "UNRESOLVED", "actor_id": ACTOR_ID},
            {"actor_hint_digest": b"raw-user"},
            {"trace_id": uuid.UUID(int=0)},
        ):
            with self.subTest(changes=changes), self.assertRaises(AuditEventValidationError):
                draft(**changes)

    def test_safe_summary_and_target_shapes(self) -> None:
        for changes in (
            {"action": "raw customer text"},
            {"reason_code": "password=secret"},
            {"before_state": "正文"},
            {"outcome": "OTHER"},
            {"target_object_id": None},
            {"target_owner_module": "../document"},
            {"target_version_id": uuid.UUID(int=0)},
        ):
            with self.subTest(changes=changes), self.assertRaises(AuditEventValidationError):
                draft(**changes)

    def test_unresolved_subject_uses_digest_only(self) -> None:
        digest = hashlib.sha256(b"synthetic-unresolved-actor").digest()
        event = draft(event_scope="DEPLOYMENT", target_project_id=None,
                      actor_type="UNRESOLVED", actor_id=None,
                      actor_hint_digest=digest, target_owner_module=None,
                      target_object_type=None, target_object_id=None,
                      before_state=None, after_state=None)
        self.assertNotIn(digest.hex(), repr(event))
        self.assertIsNone(event.actor_id)


if __name__ == "__main__":
    unittest.main()
