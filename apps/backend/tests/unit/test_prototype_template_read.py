from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

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
            repository=object(),
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


if __name__ == "__main__":
    unittest.main()
