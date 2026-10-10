from __future__ import annotations

import inspect
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.prototype.application.mark_not_required import (
    MarkPrototypeNotRequired, PrototypeScopeDecisionError,
    PrototypeScopeDecisionService, PrototypeScopeDecisionView,
)
from plm_assistant.modules.prototype.infrastructure.scope_decision_repository import (
    SqlAlchemyPrototypeScopeDecisionRepository,
)


class PrototypeScopeDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.refs = (uuid.uuid4(), uuid.uuid4())
        self.command = MarkPrototypeNotRequired(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.prototype, 0, self.refs, "No interactive flow",
            "Use standard forms", None, None, str(uuid.uuid4()),
        )
        self.service = PrototypeScopeDecisionService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_rejects_untrusted_common_and_text_input(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"prototype_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"reason": ""}, {"impact": "x" * 2001}, {"reason": "bad\x00text"},
        ):
            with self.subTest(change=change), self.assertRaises(
                PrototypeScopeDecisionError
            ) as caught:
                self.service.mark_not_required(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_requirement_scope_is_nonempty_unique_and_canonical(self) -> None:
        canonical = self.service._refs(tuple(reversed(self.refs)))
        self.assertEqual(canonical, tuple(sorted(self.refs, key=str)))
        for refs in (
            (), (uuid.UUID(int=0),), (self.refs[0], self.refs[0]),
            tuple(uuid.uuid4() for _ in range(201)),
        ):
            with self.subTest(size=len(refs)), self.assertRaises(
                PrototypeScopeDecisionError
            ) as caught:
                self.service.mark_not_required(replace(
                    self.command, affected_requirement_version_refs=refs,
                ))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_review_reference_is_an_optional_pair(self) -> None:
        self.assertEqual(self.service._review_pair(None, None), (None, None))
        for pair in ((uuid.uuid4(), None), (None, uuid.uuid4()),
                     (uuid.UUID(int=0), uuid.uuid4())):
            with self.subTest(pair=pair), self.assertRaises(
                PrototypeScopeDecisionError
            ) as caught:
                self.service._review_pair(*pair)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_view_is_fixed_and_does_not_call_pm_customer(self) -> None:
        refs = tuple(sorted(self.refs, key=str))
        view = PrototypeScopeDecisionView(
            self.prototype, self.project, "Flow", "NOT_REQUIRED", uuid.uuid4(),
            "Reason", "Impact", uuid.uuid4(), None, None, refs,
            datetime.now(timezone.utc), '"v1"',
        )
        self.assertEqual(view.affected_requirement_version_refs, refs)
        self.assertFalse(hasattr(view, "customer_confirmed"))
        with self.assertRaises(ValueError):
            replace(view, prototype_state="ACTIVE")

    def test_repository_locks_current_requirement_versions_and_root(self) -> None:
        source = inspect.getsource(SqlAlchemyPrototypeScopeDecisionRepository.decide)
        self.assertIn("with_for_update", source)
        self.assertIn('row.version_state != "APPROVED"', source)
        self.assertIn("row.current_approved_version_ref", source)
        self.assertIn('subject_type == "PRT_SCOPE_DECISION"', source)
        self.assertNotIn("delete(", source)

    def test_secret_bearing_fields_are_not_rendered(self) -> None:
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
