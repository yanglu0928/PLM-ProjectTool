"""Internal GLOBAL candidate projection and raw-root pagination contract."""

from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.solution.application.list_global_reference_candidates import (
    GlobalReferenceCandidate, GlobalReferenceCandidateCatalog,
    GlobalReferenceCandidateError, GlobalReferenceCandidatePage,
)
from plm_assistant.modules.solution.application.prove_reference_use import (
    EligibleReferenceUseProof, ReferenceUseProofError,
)


ROOT = uuid.UUID("00000000-0000-0000-0000-000000000001")
VERSION = uuid.UUID("00000000-0000-0000-0000-000000000002")
PROJECT = uuid.UUID("00000000-0000-0000-0000-000000000003")
TRACE = uuid.UUID("00000000-0000-0000-0000-000000000004")
TX = object()


class Repository:
    def __init__(self, page):
        self.page = page
        self.calls = []

    def scan(self, tx, *, after_reference_solution_id, limit):
        self.calls.append((tx, after_reference_solution_id, limit))
        return self.page


class Proof:
    def __init__(self, *, deny=False):
        self.deny = deny
        self.calls = []

    def prove(self, tx, query):
        self.calls.append((tx, query))
        if self.deny:
            raise ReferenceUseProofError()
        return EligibleReferenceUseProof(
            query.reference_solution_id, query.reference_version_id,
            "GLOBAL", query.target_project_id, b"f" * 32,
            uuid.uuid4(), uuid.uuid4())


class GlobalReferenceCandidateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.item = GlobalReferenceCandidate(ROOT, VERSION, "审定标签", 1, "ELIGIBLE")

    def test_valid_proof_yields_minimal_item(self):
        repo = Repository(GlobalReferenceCandidatePage((self.item,), None, False))
        proof = Proof()
        page = GlobalReferenceCandidateCatalog(repository=repo, proof=proof).scan(
            TX, trace_id=TRACE, project_id=PROJECT)
        self.assertEqual(page.items, (self.item,))
        self.assertEqual(repo.calls, [(TX, None, 50)])
        self.assertEqual(proof.calls[0][1].scope, "GLOBAL")
        self.assertEqual(proof.calls[0][1].target_project_id, PROJECT)
        self.assertFalse(hasattr(self.item, "name"))
        self.assertFalse(hasattr(self.item, "source_fingerprint"))

    def test_failed_current_proof_hides_item_but_preserves_raw_cursor(self):
        repo = Repository(GlobalReferenceCandidatePage((self.item,), ROOT, True))
        page = GlobalReferenceCandidateCatalog(
            repository=repo, proof=Proof(deny=True)).scan(
                TX, trace_id=TRACE, project_id=PROJECT, limit=1)
        self.assertEqual(page.items, ())
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_after_reference_solution_id, ROOT)

    def test_invalid_input_or_repository_projection_fails_closed(self):
        for value in (None, uuid.UUID(int=0), "bad"):
            with self.subTest(value=value):
                with self.assertRaises(GlobalReferenceCandidateError):
                    GlobalReferenceCandidateCatalog(
                        repository=Repository(GlobalReferenceCandidatePage((), None, False)),
                        proof=Proof()).scan(TX, trace_id=TRACE, project_id=value)
        bad = GlobalReferenceCandidate(ROOT, VERSION, "审定标签", 1, "REVOKED")
        with self.assertRaises(GlobalReferenceCandidateError):
            GlobalReferenceCandidateCatalog(
                repository=Repository(GlobalReferenceCandidatePage((bad,), None, False)),
                proof=Proof()).scan(TX, trace_id=TRACE, project_id=PROJECT)
        noncanonical = GlobalReferenceCandidate(ROOT, VERSION, "e\u0301", 1, "ELIGIBLE")
        with self.assertRaises(GlobalReferenceCandidateError):
            GlobalReferenceCandidateCatalog(
                repository=Repository(GlobalReferenceCandidatePage(
                    (noncanonical,), None, False)), proof=Proof()).scan(
                        TX, trace_id=TRACE, project_id=PROJECT)
        with self.assertRaises(GlobalReferenceCandidateError):
            GlobalReferenceCandidateCatalog(
                repository=Repository(GlobalReferenceCandidatePage((), ROOT, True)),
                proof=Proof()).scan(
                    TX, trace_id=TRACE, project_id=PROJECT,
                    after_reference_solution_id=ROOT)


if __name__ == "__main__":
    unittest.main()
