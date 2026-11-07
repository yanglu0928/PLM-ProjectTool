from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.requirement.application.read_versions import (
    RequirementAcceptanceView, RequirementSourceEvidenceView,
    RequirementSourceView,
    RequirementOutputSourceProjection, RequirementVersionPage, RequirementVersionReadError,
    RequirementVersionReadQuery, RequirementVersionReadService,
    RequirementVersionSummary, RequirementVersionView,
    RequirementVersionTraceFacts,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class RequirementVersionReadTests(unittest.TestCase):
    def setUp(self):
        self.project, self.requirement, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.actor, self.now = uuid.uuid4(), datetime.now(timezone.utc)
        self.acceptance = uuid.uuid4()
        self.summary = RequirementVersionSummary(
            self.version, self.requirement, self.project, 2, "DRAFT", None,
            "PLM", "HIGH", "MEDIUM",
            "PENDING_CONFIRMATION", "ab" * 32, 1, 1, 0, 0, 0, 0, 0,
            uuid.uuid4(), None, None, self.actor, self.now,
        )
        self.view = RequirementVersionView(
            self.summary, "Statement", "Rationale",
            (RequirementSourceView(
                0, "PROJECT_EVIDENCE", uuid.uuid4(), None,
                (RequirementSourceEvidenceView(uuid.uuid4(), 0),)),),
            (RequirementAcceptanceView(
                0, "Outcome", "Method", "Data", "Environment", "Evidence",
                self.acceptance),),
            (), (), (), (), (),
        )
        self.repo = SimpleNamespace(
            list_versions=lambda *_args, **_kwargs: (self.summary,),
            get_version=lambda *_args, **_kwargs: self.view,
            get_trace_facts=lambda *_args, **_kwargs: RequirementVersionTraceFacts(
                self.version, self.requirement, self.project, "DRAFT"),
        )
        self.query = RequirementVersionReadQuery(
            b"s" * 32, uuid.uuid4(), self.project)
        self.authorization_calls = []
        authorization = SimpleNamespace(require_in_transaction=lambda tx, **kwargs:
            (self.authorization_calls.append((tx, kwargs)) or SimpleNamespace(
                user_id=kwargs["user_id"], project_id=kwargs["project_id"],
                operation=kwargs["operation"])))
        self.service = RequirementVersionReadService(
            unit_of_work=Tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: object()),
            authorization=authorization,
            repository=self.repo, clock=lambda: self.now,
        )

    def test_list_uses_version_number_position(self):
        page = self.service.list_versions(
            self.query, requirement_id=self.requirement, page_size=10,
            after_version_no=3,
        )
        self.assertEqual(page, RequirementVersionPage((self.summary,), None, False))

    def test_get_returns_complete_fixed_snapshot(self):
        result = self.service.get_version(
            self.query, requirement_id=self.requirement,
            requirement_version_id=self.version,
        )
        self.assertEqual(result, self.view)
        self.assertEqual(result.acceptance_criteria[0].acceptance_criterion_ref,
                         self.acceptance)

    def test_trace_facts_reuse_caller_transaction_and_do_not_require_approval(self):
        tx = object()
        called = []
        self.repo.get_trace_facts = lambda transaction, **kwargs: (
            called.append((transaction, kwargs)) or RequirementVersionTraceFacts(
                self.version, self.requirement, self.project, "DRAFT"))
        facts = self.service.get_version_for_trace(
            tx, self.query, requirement_id=self.requirement,
            requirement_version_id=self.version)
        self.assertEqual(facts.version_state, "DRAFT")
        self.assertIs(called[0][0], tx)
        self.assertEqual(called[0][1]["project_id"], self.project)

    def test_trace_facts_fail_closed_for_missing_restricted_or_forged(self):
        for facts in (None, RequirementVersionTraceFacts(
                self.version, self.requirement, self.project, "RESTRICTED"),
                RequirementVersionTraceFacts(
                    self.version, self.requirement, uuid.uuid4(), "APPROVED")):
            self.repo.get_trace_facts = lambda *_a, **_k: facts
            with self.subTest(facts=facts), self.assertRaises(RequirementVersionReadError) as caught:
                self.service.get_version_for_trace(
                    object(), self.query, requirement_id=self.requirement,
                    requirement_version_id=self.version)
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_incomplete_repository_projection_fails_closed(self):
        self.repo.get_version = lambda *_a, **_k: replace(self.view, sources=())
        with self.assertRaises(RequirementVersionReadError) as caught:
            self.service.get_version(
                self.query, requirement_id=self.requirement,
                requirement_version_id=self.version,
            )
        self.assertEqual(caught.exception.code, "REQUIREMENT_UNAVAILABLE")

    def test_gapped_nested_evidence_projection_fails_closed(self):
        source = replace(
            self.view.sources[0],
            evidence_refs=(RequirementSourceEvidenceView(uuid.uuid4(), 1),),
        )
        self.repo.get_version = lambda *_a, **_k: replace(
            self.view, sources=(source,))
        with self.assertRaises(RequirementVersionReadError) as caught:
            self.service.get_version(
                self.query, requirement_id=self.requirement,
                requirement_version_id=self.version,
            )
        self.assertEqual(caught.exception.code, "REQUIREMENT_UNAVAILABLE")

    def test_invalid_cursor_and_cross_shape_are_rejected(self):
        for after in (0, -1, "2"):
            with self.assertRaises(RequirementVersionReadError):
                self.service.list_versions(
                    self.query, requirement_id=self.requirement,
                    page_size=10, after_version_no=after,
                )
        with self.assertRaises(RequirementVersionReadError):
            self.service.get_version(
                self.query, requirement_id=uuid.UUID(int=0),
                requirement_version_id=self.version,
            )

    def test_session_token_is_redacted(self):
        self.assertNotIn("s" * 32, repr(self.query))


    def test_output_source_read_rechecks_project_authorization_and_fixed_identity(self):
        self.authorization = SimpleNamespace(require_in_transaction=lambda *a, **kw:
            SimpleNamespace(user_id=self.actor, project_id=self.project, operation="REQ_VERSION_GET"))
        self.repo.get_output_source = lambda _tx, **kw: RequirementOutputSourceProjection(
            requirement_version_id=self.version, project_id=self.project,
            version_state="APPROVED", fields={"statement": "Fixed"},
        )
        projection = self.service.read_output_source(
            Tx(), actor_id=self.actor, project_id=self.project, requirement_version_id=self.version,
        )
        self.assertEqual(projection.version_state, "APPROVED")
        self.assertEqual(projection.fields["statement"], "Fixed")

    def test_output_source_reads_exact_authorized_version_and_preserves_state(self):
        fields = {"statement": "Synthetic statement"}
        projection = RequirementOutputSourceProjection(
            self.version, self.project, "IN_REVIEW", fields)
        tx = Tx()
        calls = []
        self.repo.get_output_source = lambda transaction, **kwargs: (
            calls.append((transaction, kwargs)) or projection)
        result = self.service.read_output_source(
            tx, actor_id=self.actor, project_id=self.project,
            requirement_version_id=self.version)
        self.assertIs(result, projection)
        self.assertEqual(self.authorization_calls[0], (tx, {
            "user_id": self.actor, "project_id": self.project,
            "operation": "REQ_VERSION_GET"}))
        self.assertEqual(calls[0], (tx, {
            "project_id": self.project,
            "requirement_version_id": self.version}))
        self.assertEqual(result.version_state, "IN_REVIEW")
        self.assertEqual(result.fields["statement"], "Synthetic statement")

    def test_output_source_rejects_missing_version(self):
        self.repo.get_output_source = lambda *_a, **_k: None
        with self.assertRaises(RequirementVersionReadError):
            self.service.read_output_source(
                Tx(), actor_id=self.actor, project_id=self.project, requirement_version_id=self.version,
            )

if __name__ == "__main__":
    unittest.main()
