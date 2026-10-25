from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult,
)
from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    ProvenStructuredSpecSources, StructuredSpecSourceError,
)
from plm_assistant.modules.solution.application.revise_structured_spec import (
    ReviseStructuredSpec, StructuredSpecReviseError,
    StructuredSpecReviseService,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView, StructuredSpecRevisionBase,
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
        self.original_fingerprint = None

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.scope = scope
        if self.original_fingerprint is None:
            self.original_fingerprint = request_fingerprint
        elif self.previous is not None and request_fingerprint != self.original_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return self.previous

    def complete(self, _tx, *, scope, result):
        self.completed.append(result)


class _Repository:
    def __init__(self, base):
        self.base = base
        self.view = None
        self.revised = []

    def revision_base(self, _tx, *, project_id, spec_id):
        if self.base and (self.base.project_id, self.base.structured_solution_spec_id) == (
                project_id, spec_id):
            return self.base
        return None

    def revise(self, _tx, *, base, version_id, actor_id, proof):
        self.revised.append(version_id)
        draft = proof.draft
        self.view = StructuredSpecInitialView(
            version_id, base.spec_series_id, base.project_id, base.spec_type,
            base.version_no + 1, proof.content_fingerprint, draft.payload_json,
            draft.payload_fingerprint, draft.requirement_refs, draft.section_refs,
            draft.evidence_ids, base.structured_solution_spec_id, actor_id,
            datetime.now(timezone.utc))
        return self.view

    def first_result(self, _tx, *, version_id, project_id):
        if self.view and (self.view.structured_solution_spec_id, self.view.project_id) == (
                version_id, project_id):
            return self.view
        return None


class StructuredSpecReviseTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.series, self.spec = (
            uuid.uuid4() for _ in range(4))
        self.draft = StructuredSpecDraftInput(
            self.project, None, None, "MIGRATION_SPEC", {
                "assumptions": ["synthetic pending confirmation"],
                "exclusions": [], "source_system": "old", "target_system": "new",
                "scope": "parts", "cleansing_rules": ["deduplicate"],
                "field_mappings": [{"source": "old_id", "target": "part_id"}],
                "trial_plan": "trial", "reconciliation_plan": "reconcile",
                "rollback_plan": "snapshot", "acceptance_criteria": "zero difference",
            }, (SpecRequirementRef(uuid.uuid4(), uuid.uuid4()),),
            (SpecSectionRef(uuid.uuid4(), uuid.uuid4()),), (), ())
        self.base = StructuredSpecRevisionBase(
            self.spec, self.spec, self.series, self.project,
            "MIGRATION_SPEC", 2, 2, "DRAFT")
        self.command = ReviseStructuredSpec(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.spec, self.draft, "i" * 16)
        self.tx = _Tx()
        self.receipts = _Receipts()
        self.repository = _Repository(self.base)
        self.events = []
        self.proof_calls = 0
        self.allowed = True
        self.service = StructuredSpecReviseService(
            unit_of_work=lambda: self.tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: True),
            authorization=SimpleNamespace(require_in_transaction=self._authorize),
            sources=SimpleNamespace(prove=self._prove),
            repository=self.repository, receipts=self.receipts,
            audit=SimpleNamespace(append=lambda _tx, event: self.events.append(event)))

    def _authorize(self, _tx, **_kwargs):
        return SimpleNamespace(
            user_id=self.actor, project_id=self.project,
            operation="SOL_STRUCTURED_SPEC_REVISE" if self.allowed else "DENIED")

    def _prove(self, _tx, *, draft, **_kwargs):
        self.proof_calls += 1
        return ProvenStructuredSpecSources(
            validate_structured_spec_draft(draft), (), (), (), b"p" * 32)

    def test_atomic_revision_and_exact_replay_after_later_version(self):
        first = self.service.revise(self.command)
        self.assertTrue(self.tx.committed)
        self.assertEqual((first.version_no, first.version_state), (3, "DRAFT"))
        self.assertEqual(first.supersedes_version_ref, self.spec)
        self.assertEqual(self.receipts.scope.operation,
                         "V1_SOL_STRUCTURED_SPEC_REVISE")
        self.assertEqual(self.receipts.completed[0].ref_id,
                         first.structured_solution_spec_id)
        self.assertEqual(self.events[0].action, "SOL_STRUCTURED_SPEC_REVISED")
        self.assertEqual((self.events[0].before_state, self.events[0].after_state),
                         ("DRAFT", "DRAFT"))
        self.repository.base = replace(
            self.base, structured_solution_spec_id=uuid.uuid4(),
            latest_version_ref=uuid.uuid4(), version_no=4, latest_version_no=4)
        self.tx = _Tx()
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_STRUCTURED_SPEC_REVISE",
            first.structured_solution_spec_id, 201)
        self.assertEqual(self.service.revise(replace(
            self.command, trace_id=uuid.uuid4())), first)
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.proof_calls, 1)
        self.assertEqual(len(self.events), 1)

    def test_replay_rechecks_authorization_and_body(self):
        first = self.service.revise(self.command)
        self.receipts.previous = IdempotencyResult(
            "V1_SOL_STRUCTURED_SPEC_REVISE",
            first.structured_solution_spec_id, 201)
        self.allowed = False
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.allowed = True
        changed = replace(self.draft, payload={**self.draft.payload, "scope": "changed"})
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(replace(self.command, draft=changed))
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")

    def test_rejects_client_binding_stale_state_and_type(self):
        bound = replace(
            self.draft, spec_series_id=self.series,
            supersedes_version_ref=self.spec)
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(replace(self.command, draft=bound))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        for base, code in (
            (replace(self.base, latest_version_ref=uuid.uuid4(),
                     latest_version_no=3), "VERSION_CONFLICT"),
            (replace(self.base, version_state="IN_REVIEW"), "CONFLICT_STATE"),
            (replace(self.base, version_state="RESTRICTED"), "CONFLICT_STATE"),
            (replace(self.base, spec_type="INTERFACE_SPEC"), "VALIDATION_FAILED"),
        ):
            self.tx, self.receipts, self.repository.base = _Tx(), _Receipts(), base
            self.service._receipts = self.receipts
            with self.subTest(code=code), self.assertRaises(
                    StructuredSpecReviseError) as caught:
                self.service.revise(replace(
                    self.command, idempotency_key=str(uuid.uuid4())))
            self.assertEqual(caught.exception.code, code)

    def test_missing_source_and_audit_failure_do_not_commit(self):
        self.repository.base = None
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.repository.base = self.base
        self.tx, self.receipts = _Tx(), _Receipts()
        self.service._receipts = self.receipts
        self.service._sources = SimpleNamespace(prove=lambda *_a, **_k: (
            (_ for _ in ()).throw(StructuredSpecSourceError())))
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(self.command)
        self.assertEqual(caught.exception.code, "SOURCE_UNAVAILABLE")
        self.assertFalse(self.tx.committed)
        self.tx, self.receipts = _Tx(), _Receipts()
        self.service._receipts = self.receipts
        self.service._sources = SimpleNamespace(prove=self._prove)
        self.service._audit = SimpleNamespace(append=lambda *_a, **_k: (
            (_ for _ in ()).throw(RuntimeError("audit down"))))
        with self.assertRaises(StructuredSpecReviseError) as caught:
            self.service.revise(self.command)
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
