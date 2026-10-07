from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.requirement.application.read_versions import (
    RequirementAcceptanceView, RequirementSourceEvidenceView,
    RequirementSourceView,
    RequirementVersionPage, RequirementVersionReadError,
    RequirementVersionReadQuery, RequirementVersionReadService,
    RequirementVersionSummary, RequirementVersionView,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class RequirementVersionReadTests(unittest.TestCase):
    def setUp(self):
        self.project, self.requirement, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.actor, self.now = uuid.uuid4(), datetime.now(timezone.utc)
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
                0, "Outcome", "Method", "Data", "Environment", "Evidence"),),
            (), (), (), (), (),
        )
        self.repo = SimpleNamespace(
            list_versions=lambda *_args, **_kwargs: (self.summary,),
            get_version=lambda *_args, **_kwargs: self.view,
        )
        self.query = RequirementVersionReadQuery(
            b"s" * 32, uuid.uuid4(), self.project)
        self.service = RequirementVersionReadService(
            unit_of_work=Tx,
            access=SimpleNamespace(authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: object()),
            authorization=SimpleNamespace(require_in_transaction=lambda *_a, **kwargs:
                SimpleNamespace(user_id=self.actor, project_id=self.project,
                                operation=kwargs["operation"])),
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


if __name__ == "__main__":
    unittest.main()
