from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.solution.application.create_outline_version import (
    CreateOutlineVersion, OutlineVersionCreateError,
    OutlineVersionCreateService, OutlineVersionInitialView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineVersionDraftInput, validate_outline_version_draft,
)
from plm_assistant.modules.solution.application.prove_outline_version_input import (
    ProvenOutlineVersionInput,
)


class _Tx:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self) -> None:
        self.committed = True


class _Receipts:
    def __init__(self) -> None:
        self.previous = None
        self.completed = []
        self.fingerprints = []

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.fingerprints.append(request_fingerprint)
        return self.previous

    def complete(self, _tx, *, scope, result):
        self.completed.append(result)


class _Repository:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor
        self.created = []
        self.view = None

    def create(self, _tx, *, version_id, actor_id, proof):
        self.created.append(version_id)
        draft = proof.draft
        self.view = OutlineVersionInitialView(
            version_id, draft.solution_outline_id, draft.project_id,
            proof.next_version_no, proof.content_fingerprint,
            tuple(draft.missing_declarations()), tuple(draft.conflict_declarations()),
            len(draft.section_ids), len(draft.requirement_refs),
            len(draft.reference_refs), proof.supersedes_version_id,
            actor_id, datetime.now(timezone.utc))
        return self.view

    def first_result(self, _tx, *, version_id, project_id):
        if self.view and (self.view.solution_outline_version_id == version_id
                          and self.view.project_id == project_id):
            return self.view
        return None


class OutlineVersionCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = uuid.uuid4()
        self.draft = OutlineVersionDraftInput(
            uuid.uuid4(), uuid.uuid4(), (uuid.uuid4(),), (), (),
            ({"note": "pending source"},), ())
        self.command = CreateOutlineVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.draft, "i" * 16)
        self.validated = validate_outline_version_draft(self.draft)
        self.proof = ProvenOutlineVersionInput(
            self.validated, 1, None, 0, b"p" * 32)
        self.tx = _Tx()
        self.receipts = _Receipts()
        self.repository = _Repository(self.actor)
        self.events = []
        self.proof_calls = []
        self.service = OutlineVersionCreateService(
            unit_of_work=lambda: self.tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: True),
            authorization=SimpleNamespace(require_in_transaction=lambda *_a, **_k:
                SimpleNamespace(user_id=self.actor, project_id=self.draft.project_id,
                                operation="SOL_OUTLINE_VERSION_CREATE")),
            inputs=SimpleNamespace(prove=self._prove),
            repository=self.repository, receipts=self.receipts,
            audit=SimpleNamespace(append=self._audit),
        )

    def _prove(self, _tx, **_kwargs):
        self.proof_calls.append(True)
        return self.proof

    def _audit(self, _tx, event):
        self.events.append(event)

    def test_invalid_draft_and_tokens_fail_before_io(self) -> None:
        for change in (
            {"session_token": b"short"},
            {"csrf_token": b"short"},
            {"idempotency_key": "short"},
            {"draft": replace(self.draft, section_ids=())},
        ):
            with self.subTest(change=change), self.assertRaises(OutlineVersionCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
            self.assertEqual(self.proof_calls, [])

    def test_first_create_commits_one_result_receipt_and_audit(self) -> None:
        view = self.service.create(self.command)
        self.assertTrue(self.tx.committed)
        self.assertEqual((view.version_state, view.version_no), ("DRAFT", 1))
        self.assertEqual(len(self.proof_calls), 1)
        self.assertEqual(len(self.repository.created), 1)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0].target_version_id,
                         view.solution_outline_version_id)
        self.assertEqual(self.receipts.completed[0].ref_id,
                         view.solution_outline_version_id)
        self.assertEqual(self.receipts.fingerprints,
                         [self.validated.request_fingerprint])

    def test_replay_reads_immutable_result_without_current_proof_or_new_audit(self) -> None:
        first = self.service.create(self.command)
        self.tx = _Tx()
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_OUTLINE_VERSION_CREATE", first.solution_outline_version_id, 201)
        replay = self.service.create(self.command)
        self.assertEqual(replay, first)
        self.assertFalse(self.tx.committed)
        self.assertEqual(len(self.proof_calls), 1)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(len(self.receipts.completed), 1)

    def test_audit_failure_prevents_commit_and_receipt(self) -> None:
        def fail(_tx, _event):
            raise RuntimeError("audit down")

        self.service._audit = SimpleNamespace(append=fail)
        with self.assertRaises(OutlineVersionCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "SOLUTION_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.receipts.completed, [])

    def test_command_repr_hides_tokens_and_key(self) -> None:
        rendered = repr(self.command)
        for secret in ("s" * 32, "c" * 32, "i" * 16, "pending source"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
