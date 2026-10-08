from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.prototype.api.cursors import PrototypeTemplateCursorCodec
from plm_assistant.modules.prototype.api.templates import (
    create_prototype_template_router,
)
from plm_assistant.modules.prototype.application.create_template import (
    PrototypeTemplateCreateError,
    PrototypeTemplateInitialView,
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.read_templates import (
    PrototypeTemplatePage,
    PrototypeTemplateReadError,
    PrototypeTemplateVersionView,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseError,
    PrototypeTemplateRevisionView,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, TEMPLATE, GLOBAL_TEMPLATE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
VERSION, GLOBAL_VERSION, REVISION, DOCUMENT = (
    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
)
FINGERPRINT = "a" * 64
ARTIFACTS = (TemplateArtifactRef("DOCUMENT_VERSION", DOCUMENT),)
LAYOUT = {"kind": "grid", "columns": 12}
COMPONENTS = {"allowed": ["text", "table"]}
TERMINALS = ("DESKTOP",)


def read_view(*, global_scope: bool = False) -> PrototypeTemplateVersionView:
    return PrototypeTemplateVersionView(
        GLOBAL_TEMPLATE if global_scope else TEMPLATE,
        GLOBAL_VERSION if global_scope else VERSION,
        "GLOBAL" if global_scope else "PROJECT",
        None if global_scope else PROJECT,
        "Global standard" if global_scope else "Project standard",
        "ACTIVE", 1, "PUBLISHED", None, LAYOUT, COMPONENTS, TERMINALS,
        ARTIFACTS, FINGERPRINT, 0, True, NOW, NOW,
    )


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def _page(self, global_scope, after_updated_at, after_template_id):
        if self.fail:
            raise PrototypeTemplateReadError(self.fail)
        self.after = (after_updated_at, after_template_id)
        view = read_view(global_scope=global_scope)
        more = after_updated_at is None
        return PrototypeTemplatePage(
            (view,), NOW if more else None,
            view.prototype_template_id if more else None, more,
        )

    def list_project(
        self, query, *, page_size, after_updated_at=None,
        after_template_id=None,
    ):
        self.query = query
        return self._page(False, after_updated_at, after_template_id)

    def list_global(
        self, query, *, page_size, after_updated_at=None,
        after_template_id=None,
    ):
        self.query = query
        return self._page(True, after_updated_at, after_template_id)


class Creates:
    fail = None

    def _result(self, command, *, global_scope):
        self.command = command
        if self.fail:
            raise PrototypeTemplateCreateError(self.fail)
        return PrototypeTemplateInitialView(
            GLOBAL_TEMPLATE if global_scope else TEMPLATE,
            GLOBAL_VERSION if global_scope else VERSION,
            "GLOBAL" if global_scope else "PROJECT",
            None if global_scope else PROJECT,
            command.name, 1, command.layout_contract,
            command.component_contract, command.applicable_terminals,
            command.artifact_refs, FINGERPRINT, NOW,
        )

    def create_project(self, command):
        return self._result(command, global_scope=False)

    def create_global(self, command):
        return self._result(command, global_scope=True)


class Revisions:
    fail = None

    def _result(self, command, *, global_scope):
        self.command = command
        if self.fail:
            raise PrototypeTemplateReviseError(self.fail)
        return PrototypeTemplateRevisionView(
            GLOBAL_TEMPLATE if global_scope else TEMPLATE,
            REVISION,
            GLOBAL_VERSION if global_scope else VERSION,
            "GLOBAL" if global_scope else "PROJECT",
            None if global_scope else PROJECT,
            "Global standard" if global_scope else "Project standard",
            2, command.layout_contract, command.component_contract,
            command.applicable_terminals, command.artifact_refs,
            FINGERPRINT, 1, NOW,
        )

    def revise_project(self, command):
        return self._result(command, global_scope=False)

    def revise_global(self, command):
        return self._result(command, global_scope=True)


class PrototypeTemplateApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.revisions = Reads(), Creates(), Revisions()
        self.reads.fail = self.creates.fail = self.revisions.fail = None
        router = create_prototype_template_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, creates=self.creates, revisions=self.revisions,
            cursors=PrototypeTemplateCursorCodec(b"t" * 32),
        )
        self.client = TestClient(
            create_app(prototype_template_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.project_root = (
            f"/api/v1/projects/{PROJECT}/prototype-templates"
        )
        self.global_root = "/api/v1/global/prototype-templates"
        self.project_revise = f"{self.project_root}/{TEMPLATE}:revise"
        self.global_revise = f"{self.global_root}/{GLOBAL_TEMPLATE}:revise"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers,
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.create_body = {
            "name": "Project standard",
            "layout_contract": LAYOUT,
            "component_contract": COMPONENTS,
            "applicable_terminals": list(TERMINALS),
            "artifact_refs": [{
                "artifact_kind": "DOCUMENT_VERSION",
                "target_id": str(DOCUMENT),
            }],
        }
        self.revise_body = {
            key: value for key, value in self.create_body.items()
            if key != "name"
        }

    def test_default_closed_and_six_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for path in (self.project_root, self.global_root):
                self.assertEqual(404, bare.get(path).status_code)
                self.assertEqual(404, bare.post(path).status_code)
            self.assertEqual(404, bare.post(self.project_revise).status_code)
            self.assertEqual(404, bare.post(self.global_revise).status_code)

        for path, expected_scope in (
            (self.project_root, "PROJECT"), (self.global_root, "GLOBAL"),
        ):
            first = self.client.get(
                path + "?page_size=1", headers=self.read_headers,
            )
            self.assertEqual(200, first.status_code)
            self.assertEqual(expected_scope, first.json()["data"]["items"][0]["scope"])
            cursor = first.json()["data"]["next_cursor"]
            second = self.client.get(
                path + f"?page_size=1&cursor={cursor}",
                headers=self.read_headers,
            )
            self.assertEqual(200, second.status_code)
            self.assertFalse(second.json()["data"]["has_more"])

        project_created = self.client.post(
            self.project_root, headers=self.write_headers,
            json=self.create_body,
        )
        self.assertEqual(201, project_created.status_code)
        self.assertEqual("PROJECT", project_created.json()["data"]["scope"])
        global_body = {**self.create_body, "name": "Global standard"}
        global_created = self.client.post(
            self.global_root, headers=self.write_headers, json=global_body,
        )
        self.assertEqual(201, global_created.status_code)
        self.assertEqual("GLOBAL", global_created.json()["data"]["scope"])

        project_revised = self.client.post(
            self.project_revise, headers=self.write_headers,
            json=self.revise_body,
        )
        self.assertEqual(201, project_revised.status_code)
        self.assertEqual(2, project_revised.json()["data"]["version_no"])
        global_revised = self.client.post(
            self.global_revise, headers=self.write_headers,
            json=self.revise_body,
        )
        self.assertEqual(201, global_revised.status_code)
        self.assertEqual('"v1"', global_revised.headers["etag"])

    def test_security_preconditions_and_strict_body(self):
        self.assertEqual(401, self.client.get(self.project_root).status_code)
        self.assertEqual(403, self.client.post(
            self.project_root,
            headers={**self.write_headers, "origin": "https://evil.test"},
            json=self.create_body,
        ).status_code)
        no_key = {
            key: value for key, value in self.write_headers.items()
            if key != "idempotency-key"
        }
        self.assertEqual(422, self.client.post(
            self.global_root, headers=no_key, json=self.create_body,
        ).status_code)
        no_match = {
            key: value for key, value in self.write_headers.items()
            if key != "if-match"
        }
        self.assertEqual(428, self.client.post(
            self.project_revise, headers=no_match, json=self.revise_body,
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.project_root, headers=self.write_headers,
            json={**self.create_body, "scope": "GLOBAL"},
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.project_root, headers=self.write_headers,
            json={**self.create_body, "applicable_terminals": "DESKTOP"},
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.global_root + "?page_size=1&page_size=1",
            headers=self.read_headers,
        ).status_code)

    def test_cursor_scope_and_output_identity_fail_closed(self):
        first = self.client.get(
            self.global_root + "?page_size=1", headers=self.read_headers,
        )
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            self.project_root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers,
        ).status_code)
        original_list = self.reads.list_project
        invalid_view = PrototypeTemplateVersionView(
            TEMPLATE, VERSION, "PROJECT", PROJECT, "Project standard",
            "ACTIVE", 1, "PUBLISHED", None, LAYOUT, COMPONENTS, TERMINALS,
            (TemplateArtifactRef("INVALID", DOCUMENT),), FINGERPRINT, 0,
            True, NOW, NOW,
        )
        self.reads.list_project = lambda *_a, **_k: PrototypeTemplatePage(
            (invalid_view,), None, None, False,
        )
        self.assertEqual(503, self.client.get(
            self.project_root, headers=self.read_headers,
        ).status_code)
        self.reads.list_project = original_list
        original = self.creates.create_project
        self.creates.create_project = lambda command: PrototypeTemplateInitialView(
            TEMPLATE, VERSION, "PROJECT", uuid.uuid4(), command.name, 1,
            command.layout_contract, command.component_contract,
            command.applicable_terminals, command.artifact_refs,
            FINGERPRINT, NOW,
        )
        self.assertEqual(503, self.client.post(
            self.project_root, headers=self.write_headers,
            json=self.create_body,
        ).status_code)
        self.creates.create_project = original

    def test_safe_error_mapping(self):
        cases = (
            (self.reads, "AUTH_ACCESS_DENIED", "read", 404),
            (self.creates, "PROTOTYPE_ARTIFACT_UNAVAILABLE", "create", 404),
            (self.creates, "CONFLICT_IDEMPOTENCY", "create", 409),
            (self.revisions, "VERSION_CONFLICT", "revise", 409),
            (self.revisions, "PROTOTYPE_STATE_CONFLICT", "revise", 409),
        )
        for owner, code, operation, status in cases:
            with self.subTest(code=code):
                owner.fail = code
                if operation == "read":
                    response = self.client.get(
                        self.project_root, headers=self.read_headers,
                    )
                elif operation == "create":
                    response = self.client.post(
                        self.project_root, headers=self.write_headers,
                        json=self.create_body,
                    )
                else:
                    response = self.client.post(
                        self.project_revise, headers=self.write_headers,
                        json=self.revise_body,
                    )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                owner.fail = None


if __name__ == "__main__":
    unittest.main()
