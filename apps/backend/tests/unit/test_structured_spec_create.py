from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.solution.application.create_structured_spec import (
    CreateStructuredSpec, StructuredSpecCreateError, StructuredSpecCreateService,
)
from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    ProvenStructuredSpecSources, StructuredSpecSourceError,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView,
)


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.committed = True


class _Receipts:
    def __init__(self):
        self.previous = None
        self.completed = []

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.fingerprint = request_fingerprint
        self.scope = scope
        return self.previous

    def complete(self, _tx, *, scope, result):
        self.completed.append(result)


class _Repository:
    def __init__(self):
        self.view = None
        self.created = []

    def create(self, _tx, *, version_id, actor_id, proof):
        self.created.append(version_id)
        draft = proof.draft
        self.view = StructuredSpecInitialView(
            version_id, draft.spec_series_id or uuid.uuid4(), draft.project_id,
            draft.spec_type, 1, proof.content_fingerprint, draft.payload_json,
            draft.payload_fingerprint, draft.requirement_refs, draft.section_refs,
            draft.evidence_ids, draft.supersedes_version_ref, actor_id,
            datetime.now(timezone.utc))
        return self.view

    def first_result(self, _tx, *, version_id, project_id):
        if self.view and (self.view.structured_solution_spec_id == version_id
                          and self.view.project_id == project_id):
            return self.view
        return None


class StructuredSpecCreateTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        self.draft = StructuredSpecDraftInput(
            uuid.uuid4(), None, None, "MIGRATION_SPEC", {
                "assumptions": ["synthetic pending confirmation"],
                "exclusions": [], "source_system": "old", "target_system": "new",
                "scope": "parts", "cleansing_rules": ["deduplicate"],
                "field_mappings": [{"source": "old_id", "target": "part_id"}],
                "trial_plan": "trial", "reconciliation_plan": "reconcile",
                "rollback_plan": "snapshot", "acceptance_criteria": "zero difference",
            }, (SpecRequirementRef(uuid.uuid4(), uuid.uuid4()),),
            (SpecSectionRef(uuid.uuid4(), uuid.uuid4()),), (), ())
        self.validated = validate_structured_spec_draft(self.draft)
        self.command = CreateStructuredSpec(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.draft, "i" * 16)
        self.tx = _Tx()
        self.receipts = _Receipts()
        self.repository = _Repository()
        self.events = []
        self.proof_calls = 0
        self.allowed = True
        self.proof = ProvenStructuredSpecSources(
            self.validated, (), (), (), b"p" * 32)
        self.service = StructuredSpecCreateService(
            unit_of_work=lambda: self.tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: True),
            authorization=SimpleNamespace(require_in_transaction=self._authorize),
            sources=SimpleNamespace(prove=self._prove),
            repository=self.repository, receipts=self.receipts,
            audit=SimpleNamespace(append=lambda _tx, event: self.events.append(event)))

    def _authorize(self, _tx, **_kwargs):
        return SimpleNamespace(user_id=self.actor, project_id=self.draft.project_id,
                               operation=("SOL_STRUCTURED_SPEC_CREATE"
                                          if self.allowed else "DENIED"))

    def _prove(self, _tx, **_kwargs):
        self.proof_calls += 1
        return self.proof

    def test_atomic_create_and_exact_replay(self):
        first = self.service.create(self.command)
        self.assertTrue(self.tx.committed)
        self.assertEqual((first.version_state, first.version_no), ("DRAFT", 1))
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0].target_object_id, first.spec_series_id)
        self.assertEqual(self.events[0].target_version_id,
                         first.structured_solution_spec_id)
        self.assertEqual(self.receipts.completed[0].ref_id,
                         first.structured_solution_spec_id)
        self.assertEqual(self.receipts.fingerprint,
                         self.validated.request_fingerprint)
        self.tx = _Tx()
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_STRUCTURED_SPEC_CREATE", first.structured_solution_spec_id, 201)
        self.assertEqual(self.service.create(self.command), first)
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.proof_calls, 1)
        self.assertEqual(len(self.events), 1)

    def test_replay_rechecks_authorization(self):
        first = self.service.create(self.command)
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_STRUCTURED_SPEC_CREATE", first.structured_solution_spec_id, 201)
        self.allowed = False
        with self.assertRaises(StructuredSpecCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.proof_calls, 1)

    def test_invalid_command_before_io(self):
        for change in ({"session_token": b"short"}, {"csrf_token": b"short"},
                       {"idempotency_key": "short"}):
            with self.subTest(change=change), self.assertRaises(StructuredSpecCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(len(self.repository.created), 0)

    def test_proof_or_audit_failure_does_not_commit(self):
        self.service._sources = SimpleNamespace(prove=lambda *_a, **_k: (
            (_ for _ in ()).throw(StructuredSpecSourceError())))
        with self.assertRaises(StructuredSpecCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "SOURCE_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.service._sources = SimpleNamespace(prove=self._prove)
        self.service._audit = SimpleNamespace(append=lambda *_a, **_k: (
            (_ for _ in ()).throw(RuntimeError("audit down"))))
        with self.assertRaises(StructuredSpecCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "SOLUTION_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.receipts.completed, [])

    def test_repr_hides_sensitive_material(self):
        rendered = repr(self.command)
        for value in ("s" * 32, "c" * 32, "i" * 16,
                      "synthetic pending confirmation"):
            self.assertNotIn(value, rendered)


if __name__ == "__main__":
    unittest.main()
