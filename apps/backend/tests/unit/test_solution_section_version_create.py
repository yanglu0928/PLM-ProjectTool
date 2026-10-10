from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.solution.application.create_section_version import (
    CreateSectionVersion, SectionVersionCreateError,
    SectionVersionCreateService, SectionVersionInitialView,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentProof,
)
from plm_assistant.modules.solution.application.prove_section_version_input import (
    ProvenSectionVersionInput, SectionVersionInputProofError,
)
from plm_assistant.modules.solution.application.section_version_base import (
    CurrentSectionVersionBase,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionVersionDraftInput, validate_section_version_draft,
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
    def __init__(self) -> None:
        self.created = []
        self.view = None

    def create(self, _tx, *, version_id, actor_id, proof):
        self.created.append(version_id)
        draft = proof.draft
        self.view = SectionVersionInitialView(
            version_id, draft.solution_section_id, draft.project_id,
            proof.base.next_version_no, draft.title,
            draft.content_document_version_ref, proof.content_fingerprint,
            draft.requirement_refs, draft.evidence_ids,
            tuple(draft.assumptions()), tuple(draft.exclusions()),
            proof.base.supersedes_version_id, actor_id,
            datetime.now(timezone.utc))
        return self.view

    def first_result(self, _tx, *, version_id, project_id):
        if self.view and (self.view.solution_section_version_id == version_id
                          and self.view.project_id == project_id):
            return self.view
        return None


class SectionVersionCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = uuid.uuid4()
        self.outline_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.draft = SectionVersionDraftInput(
            uuid.uuid4(), uuid.uuid4(), "Draft section", uuid.uuid4(),
            None, (), (), ({"note": "source pending review"},), ())
        self.command = CreateSectionVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.draft, "i" * 16)
        self.validated = validate_section_version_draft(self.draft)
        self.proof = ProvenSectionVersionInput(
            self.validated,
            CurrentSectionVersionBase(self.draft.project_id, self.outline_id,
                                      self.draft.solution_section_id, 1, None, 0, 0),
            SectionDocumentContentProof(self.draft.project_id, self.document_id,
                                        self.draft.content_document_version_ref,
                                        b"d" * 32),
            (), (), b"p" * 32)
        self.tx = _Tx()
        self.receipts = _Receipts()
        self.repository = _Repository()
        self.events = []
        self.proof_calls = []
        self.authorized = True
        self.service = SectionVersionCreateService(
            unit_of_work=lambda: self.tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: True),
            authorization=SimpleNamespace(require_in_transaction=self._authorize),
            inputs=SimpleNamespace(prove=self._prove),
            repository=self.repository, receipts=self.receipts,
            audit=SimpleNamespace(append=self._audit),
        )

    def _authorize(self, _tx, **_kwargs):
        return SimpleNamespace(
            user_id=self.actor, project_id=self.draft.project_id,
            operation=("SOL_SECTION_VERSION_CREATE" if self.authorized else "DENIED"))

    def _prove(self, _tx, **_kwargs):
        self.proof_calls.append(True)
        return self.proof

    def _audit(self, _tx, event):
        self.events.append(event)

    def test_invalid_command_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"},
            {"csrf_token": b"short"},
            {"idempotency_key": "short"},
            {"draft": replace(self.draft, content_document_version_ref=None)},
        ):
            with self.subTest(change=change), self.assertRaises(SectionVersionCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
            self.assertEqual(self.proof_calls, [])

    def test_first_create_commits_result_receipt_and_one_audit(self) -> None:
        view = self.service.create(self.command)
        self.assertTrue(self.tx.committed)
        self.assertEqual((view.version_state, view.version_no), ("DRAFT", 1))
        self.assertEqual(len(self.proof_calls), 1)
        self.assertEqual(len(self.repository.created), 1)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0].target_version_id,
                         view.solution_section_version_id)
        self.assertEqual(self.receipts.completed[0].ref_id,
                         view.solution_section_version_id)
        self.assertEqual(self.receipts.fingerprints,
                         [self.validated.request_fingerprint])

    def test_replay_skips_source_proof_and_new_audit(self) -> None:
        first = self.service.create(self.command)
        self.tx = _Tx()
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_SECTION_VERSION_CREATE", first.solution_section_version_id, 201)
        replay = self.service.create(self.command)
        self.assertEqual(replay, first)
        self.assertFalse(self.tx.committed)
        self.assertEqual(len(self.proof_calls), 1)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(len(self.receipts.completed), 1)

    def test_replay_still_rechecks_current_project_authorization(self) -> None:
        first = self.service.create(self.command)
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_SECTION_VERSION_CREATE", first.solution_section_version_id, 201)
        self.authorized = False
        with self.assertRaises(SectionVersionCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(len(self.proof_calls), 1)

    def test_proof_and_audit_failure_prevent_commit(self) -> None:
        self.service._inputs = SimpleNamespace(prove=lambda *_a, **_k: (
            (_ for _ in ()).throw(SectionVersionInputProofError())))
        with self.assertRaises(SectionVersionCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "SOURCE_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.receipts.completed, [])
        self.service._inputs = SimpleNamespace(prove=self._prove)
        self.service._audit = SimpleNamespace(append=lambda *_a, **_k: (
            (_ for _ in ()).throw(RuntimeError("audit down"))))
        with self.assertRaises(SectionVersionCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "SOLUTION_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.receipts.completed, [])

    def test_command_repr_hides_tokens_key_and_source_text(self) -> None:
        rendered = repr(self.command)
        for secret in ("s" * 32, "c" * 32, "i" * 16,
                       "source pending review"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
