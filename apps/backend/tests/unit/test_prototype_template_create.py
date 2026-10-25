from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.prototype.application.create_template import (
    CreateGlobalPrototypeTemplate, CreateProjectPrototypeTemplate,
    PrototypeTemplateCreateError, PrototypeTemplateCreateService,
    PrototypeTemplateInitialView, TemplateArtifactRef,
)


class PrototypeTemplateCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document_version = uuid.uuid4()
        common = dict(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            trace_id=uuid.uuid4(), name="Desktop review",
            layout_contract={"schema": 1, "regions": ["main"]},
            component_contract={"schema": 1, "components": ["form"]},
            applicable_terminals=("DESKTOP_WEB",),
            artifact_refs=(TemplateArtifactRef(
                "DOCUMENT_VERSION", self.document_version,
            ),), idempotency_key=str(uuid.uuid4()),
        )
        self.project = CreateProjectPrototypeTemplate(
            project_id=uuid.uuid4(), **common,
        )
        self.global_command = CreateGlobalPrototypeTemplate(**common)
        self.service = PrototypeTemplateCreateService(
            unit_of_work=lambda: None, project_access=object(),
            admin_access=object(), license_guard=object(), authorization=object(),
            document_artifacts=object(), repository=object(), receipts=object(),
            audit=object(),
        )

    def test_untrusted_shape_and_active_content_fail_before_io(self) -> None:
        cases = (
            replace(self.project, session_token=b"short"),
            replace(self.project, csrf_token=b"short"),
            replace(self.project, trace_id=uuid.UUID(int=0)),
            replace(self.project, project_id=uuid.UUID(int=0)),
            replace(self.project, name="bad\x00name"),
            replace(self.project, layout_contract={"script": "alert(1)"}),
            replace(self.project, layout_contract={"action": "javascript:alert(1)"}),
            replace(self.project, component_contract=[]),
            replace(self.project, applicable_terminals=()),
            replace(self.project, applicable_terminals=("desktop",)),
            replace(self.project, artifact_refs=(
                TemplateArtifactRef("OTHER", uuid.uuid4()),
            )),
            replace(self.project, idempotency_key="short"),
        )
        for command in cases:
            with self.subTest(command=command), self.assertRaises(
                PrototypeTemplateCreateError,
            ) as caught:
                self.service.create_project(command)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_contract_and_collections_are_canonical(self) -> None:
        self.assertEqual(
            self.service._contract({"b": 2, "a": [True, None], "one": 1}),
            {"a": [True, None], "b": 2, "one": 1},
        )
        with self.assertRaisesRegex(PrototypeTemplateCreateError, "VALIDATION_FAILED"):
            self.service._contract({"onClick": "handler"})
        self.assertEqual(
            self.service._terminals(("TABLET_WEB", "DESKTOP_WEB")),
            ("DESKTOP_WEB", "TABLET_WEB"),
        )
        refs = (
            TemplateArtifactRef("DOCUMENT_VERSION", uuid.UUID(int=2)),
            TemplateArtifactRef("DOCUMENT_VERSION", uuid.UUID(int=1)),
        )
        self.assertEqual(
            tuple(item.target_id.int for item in self.service._artifacts(refs)),
            (1, 2),
        )

    def test_initial_view_fixes_first_published_version(self) -> None:
        view = PrototypeTemplateInitialView(
            uuid.uuid4(), uuid.uuid4(), "PROJECT", self.project.project_id,
            "Template", 1, {"schema": 1}, {"schema": 1},
            ("DESKTOP_WEB",), (), "0" * 64, datetime.now(timezone.utc),
        )
        self.assertEqual(
            (view.template_state, view.version_state, view.etag),
            ("ACTIVE", "PUBLISHED", '"v0"'),
        )
        with self.assertRaises(ValueError):
            replace(view, version_no=2)

    def test_secrets_and_idempotency_keys_are_redacted(self) -> None:
        for command in (self.project, self.global_command):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            self.assertNotIn(command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
