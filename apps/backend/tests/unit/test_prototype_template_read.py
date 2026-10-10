from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.prototype.application.create_template import (
    TemplateArtifactRef,
)

from plm_assistant.modules.prototype.application.read_templates import (
    GlobalPrototypeTemplateReadQuery, ProjectPrototypeTemplateReadQuery,
    PrototypeTemplateReadError, PrototypeTemplateReadService,
    PrototypeTemplateVersionView,
)


class PrototypeTemplateReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PrototypeTemplateReadService(
            unit_of_work=lambda: None, project_access=object(),
            admin_access=object(), license_guard=object(), authorization=object(),
            repository=object(), documents=object(),
        )

    def test_query_cursor_and_identity_validation_fail_closed(self) -> None:
        project = ProjectPrototypeTemplateReadQuery(
            b"s" * 32, uuid.uuid4(), uuid.uuid4(),
        )
        with self.assertRaisesRegex(PrototypeTemplateReadError, "VALIDATION_FAILED"):
            self.service.list_project(project, page_size=0)
        with self.assertRaisesRegex(PrototypeTemplateReadError, "VALIDATION_FAILED"):
            self.service.list_project(
                project, page_size=20, after_updated_at=datetime.now(timezone.utc),
            )
        with self.assertRaisesRegex(PrototypeTemplateReadError, "RESOURCE_NOT_FOUND"):
            self.service.get_project_version(
                project, template_id=uuid.UUID(int=0), version_id=uuid.uuid4(),
            )
        with self.assertRaisesRegex(PrototypeTemplateReadError, "VALIDATION_FAILED"):
            self.service.list_global(
                GlobalPrototypeTemplateReadQuery(b"short", uuid.uuid4()), page_size=20,
            )

    def test_version_view_distinguishes_historical_version_from_root_etag(self) -> None:
        project = uuid.uuid4()
        view = PrototypeTemplateVersionView(
            uuid.uuid4(), uuid.uuid4(), "PROJECT", project, "Template", "ACTIVE",
            2, "PUBLISHED", uuid.uuid4(), {"schema": 2}, {"schema": 2},
            ("DESKTOP_WEB",), (), "0" * 64, 3, False,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
        )
        self.assertEqual(view.etag, '"v3"')
        self.assertFalse(view.is_current)
        with self.assertRaises(ValueError):
            PrototypeTemplateVersionView(
                view.prototype_template_id, view.prototype_template_version_id,
                "GLOBAL", project, view.name, view.template_state, view.version_no,
                view.version_state, view.supersedes_version_id,
                view.layout_contract, view.component_contract,
                view.applicable_terminals, view.artifact_refs,
                view.content_fingerprint, view.root_lock_version, view.is_current,
                view.root_updated_at, view.version_created_at,
            )

    def test_document_artifact_gets_safe_business_locator(self) -> None:
        project, document, version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.service._documents = SimpleNamespace(prove=lambda *_a, **kwargs:
            SimpleNamespace(
                document_version_id=kwargs["document_version_id"],
                document_id=document, scope=kwargs["template_scope"],
                project_id=kwargs["project_id"],
            ))
        view = PrototypeTemplateVersionView(
            uuid.uuid4(), uuid.uuid4(), "PROJECT", project, "Template", "ACTIVE",
            1, "PUBLISHED", None, {"schema": 1}, {"schema": 1},
            ("DESKTOP_WEB",), (TemplateArtifactRef("DOCUMENT_VERSION", version),),
            "0" * 64, 0, True, datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )
        located = self.service._located(object(), view)
        self.assertEqual(document, located.artifact_refs[0].document_id)
        self.assertEqual(version, located.artifact_refs[0].target_id)


if __name__ == "__main__":
    unittest.main()
