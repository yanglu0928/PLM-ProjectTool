from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.prototype.application.create_template import (
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseError, PrototypeTemplateReviseService,
    PrototypeTemplateRevisionView, ReviseGlobalPrototypeTemplate,
    ReviseProjectPrototypeTemplate,
)


class PrototypeTemplateReviseTests(unittest.TestCase):
    def setUp(self) -> None:
        common = dict(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            trace_id=uuid.uuid4(), prototype_template_id=uuid.uuid4(),
            expected_lock_version=0,
            layout_contract={"schema": 2, "regions": ["main"]},
            component_contract={"schema": 2, "components": ["form"]},
            applicable_terminals=("DESKTOP_WEB",),
            artifact_refs=(TemplateArtifactRef(
                "DOCUMENT_VERSION", uuid.uuid4(),
            ),), idempotency_key=str(uuid.uuid4()),
        )
        self.project = ReviseProjectPrototypeTemplate(
            project_id=uuid.uuid4(), **common,
        )
        self.global_command = ReviseGlobalPrototypeTemplate(**common)
        self.service = PrototypeTemplateReviseService(
            unit_of_work=lambda: None, project_access=object(),
            admin_access=object(), license_guard=object(), authorization=object(),
            document_artifacts=object(), repository=object(), receipts=object(),
            audit=object(),
        )

    def test_invalid_identity_version_and_contract_fail_before_io(self) -> None:
        cases = (
            replace(self.project, session_token=b"short"),
            replace(self.project, csrf_token=b"short"),
            replace(self.project, prototype_template_id=uuid.UUID(int=0)),
            replace(self.project, expected_lock_version=-1),
            replace(self.project, expected_lock_version=True),
            replace(self.project, layout_contract={"onclick": "handler"}),
            replace(self.project, applicable_terminals=()),
            replace(self.project, idempotency_key="short"),
        )
        for command in cases:
            with self.subTest(command=command), self.assertRaises(
                PrototypeTemplateReviseError,
            ) as caught:
                self.service.revise_project(command)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_revision_view_binds_chain_and_root_etag(self) -> None:
        view = PrototypeTemplateRevisionView(
            self.project.prototype_template_id, uuid.uuid4(), uuid.uuid4(),
            "PROJECT", self.project.project_id, "Template", 2,
            {"schema": 2}, {"schema": 2}, ("DESKTOP_WEB",), (),
            "0" * 64, 1, datetime.now(timezone.utc),
        )
        self.assertEqual(view.etag, '"v1"')
        with self.assertRaises(ValueError):
            replace(view, lock_version=2)

    def test_secret_fields_are_redacted(self) -> None:
        for command in (self.project, self.global_command):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            self.assertNotIn(command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
