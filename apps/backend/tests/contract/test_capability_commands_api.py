from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.capability.api.commands import create_capability_command_router
from plm_assistant.modules.capability.application.change_state import (
    CapabilityStateError, RestrictedCapabilityVersion,
)
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateError, CapabilityBaselineInitialView,
)
from plm_assistant.modules.capability.application.create_version import (
    CapabilityVersionCreateError, CreatedCapabilityVersion,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityVersionView,
)
from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionValidationError, CapabilityVersionValidationReport,
)


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
BASELINE = uuid.uuid4()
VERSION = uuid.uuid4()
DOCUMENT = uuid.uuid4()
DOCUMENT_VERSION = uuid.uuid4()
EVIDENCE = uuid.uuid4()
ITEM = uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Baselines:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise CapabilityBaselineCreateError(self.fail)
        return CapabilityBaselineInitialView(
            BASELINE, "PLM.CORE", "PLM Core", None, "sha256:" + "a" * 64, NOW,
        )


class Versions:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise CapabilityVersionCreateError(self.fail)
        return CreatedCapabilityVersion(
            VERSION, BASELINE, 1, "DRAFT", "sha256:" + "a" * 64,
            b"b" * 32, None, uuid.uuid4(), NOW, 0, 1,
        )


class Validations:
    def __init__(self):
        self.last = None
        self.fail = None

    def validate(self, command):
        self.last = command
        if self.fail:
            raise CapabilityVersionValidationError(self.fail)
        return CapabilityVersionValidationReport(
            uuid.uuid4(), command.trace_id, BASELINE, VERSION, 1, "DRAFT",
            "sha256:" + "a" * 64, b"b" * 32, 1, 1, 1, True, (), NOW,
        )


def baseline_view(state="ACTIVE", etag='"v1"'):
    return CapabilityBaselineView(
        BASELINE, "PLM.CORE", "PLM Core", "Detail", state,
        "sha256:" + "a" * 64, None, NOW, NOW, etag,
    )


def version_view(state="RESTRICTED"):
    return CapabilityVersionView(
        VERSION, BASELINE, 1, state, "sha256:" + "a" * 64, "b" * 64,
        1, 1, 1, None, None, None, NOW,
    )


class States:
    def __init__(self):
        self.last = None
        self.fail = None

    def _check(self, command):
        self.last = command
        if self.fail:
            raise CapabilityStateError(self.fail)

    def patch(self, command):
        self._check(command)
        return baseline_view()

    def archive(self, command):
        self._check(command)
        return baseline_view("ARCHIVED")

    def restrict(self, command):
        self._check(command)
        return RestrictedCapabilityVersion(version_view(), command.reason_code)


class CapabilityCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.baselines, self.versions = Baselines(), Versions()
        self.validations, self.states = Validations(), States()
        router = create_capability_command_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            baselines=self.baselines, versions=self.versions,
            validations=self.validations, states=self.states,
        )
        self.client = TestClient(
            create_app(capability_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = "/api/v1/global/capability-baselines"
        self.baseline_path = f"{self.root}/{BASELINE}"
        self.version_path = f"{self.baseline_path}/versions/{VERSION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.source = {
            "document_id": str(DOCUMENT),
            "document_version_id": str(DOCUMENT_VERSION),
        }
        self.baseline_body = {
            "baseline_code": "PLM.CORE", "name": "PLM Core",
            "description": None, "source_documents": [self.source],
        }
        self.item = {
            "stable_item_id": str(ITEM), "capability_code": "PLM.CORE.ITEM",
            "domain_name": "PLM", "module_name": "Core",
            "feature_name": "Identity", "name": "Identity",
            "description": "Synthetic", "boundary": "Synthetic only",
            "prerequisites": ["CONFIGURED"], "interface_refs": ["IF-01"],
            "document_refs": [self.source], "evidence_refs": [str(EVIDENCE)],
            "item_state": "AVAILABLE",
        }

    def test_default_closed_and_all_six_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.root).status_code, 404)
            self.assertEqual(bare.patch(self.baseline_path).status_code, 404)
            self.assertEqual(bare.post(self.baseline_path + ":archive").status_code, 404)
            self.assertEqual(bare.post(self.baseline_path + "/versions").status_code, 404)
            self.assertEqual(bare.post(self.version_path + ":validate").status_code, 404)
            self.assertEqual(bare.post(self.version_path + ":restrict").status_code, 404)

        created = self.client.post(self.root, headers=self.headers, json=self.baseline_body)
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.baseline_path, created.headers["location"])

        patched = self.client.patch(
            self.baseline_path, headers=self.headers, json={"description": "Detail"},
        )
        self.assertEqual(200, patched.status_code)
        self.assertFalse(self.states.last.patch_name)
        self.assertTrue(self.states.last.patch_description)
        self.assertEqual('"v1"', patched.headers["etag"])

        archived = self.client.post(
            self.baseline_path + ":archive", headers=self.headers, content=b"",
        )
        self.assertEqual(200, archived.status_code)
        self.assertEqual("ARCHIVED", archived.json()["data"]["state"])

        version = self.client.post(
            self.baseline_path + "/versions", headers=self.headers,
            json={"items": [self.item]},
        )
        self.assertEqual(201, version.status_code)
        self.assertEqual('"v1"', version.headers["etag"])
        self.assertEqual(self.version_path, version.headers["location"])
        self.assertEqual(ITEM, self.versions.last.items[0].capability_item_id)

        validated = self.client.post(
            self.version_path + ":validate", headers=self.headers, content=b"",
        )
        self.assertEqual(200, validated.status_code)
        self.assertTrue(validated.json()["data"]["valid"])
        self.assertEqual([], validated.json()["data"]["blocking_issues"])

        restricted = self.client.post(
            self.version_path + ":restrict", headers=self.headers,
            json={"reason_code": "SOURCE_WITHDRAWN"},
        )
        self.assertEqual(200, restricted.status_code)
        self.assertEqual("RESTRICTED", restricted.json()["data"]["state"])
        self.assertEqual("SOURCE_WITHDRAWN", restricted.json()["data"]["reason_code"])

    def test_security_headers_query_and_json_are_fail_closed(self):
        bad_origin = {**self.headers, "origin": "https://evil.test"}
        self.assertEqual(403, self.client.post(
            self.root, headers=bad_origin, json=self.baseline_body,
        ).status_code)
        no_key = {key: value for key, value in self.headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.root, headers=no_key, json=self.baseline_body,
        ).status_code)
        no_match = {key: value for key, value in self.headers.items() if key != "if-match"}
        self.assertEqual(428, self.client.patch(
            self.baseline_path, headers=no_match, json={"name": "New"},
        ).status_code)
        self.assertEqual(400, self.client.patch(
            self.baseline_path, headers=self.headers, json={},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root + "?bad=1", headers=self.headers, json=self.baseline_body,
        ).status_code)
        duplicate = (
            b'{"baseline_code":"A","baseline_code":"B","name":"N",'
            b'"description":null,"source_documents":[]}'
        )
        self.assertEqual(400, self.client.post(self.root, headers={
            **self.headers, "content-type": "application/json",
        }, content=duplicate).status_code)
        self.assertEqual(422, self.client.post(
            self.root + "/" + str(BASELINE).upper() + "/versions",
            headers=self.headers, json={"items": [self.item]},
        ).status_code)

    def test_error_mapping_is_stable_and_safe(self):
        self.baselines.fail = "AUTH_ACCESS_DENIED"
        response = self.client.post(self.root, headers=self.headers, json=self.baseline_body)
        self.assertEqual(404, response.status_code)
        self.assertEqual("RESOURCE_NOT_FOUND", response.json()["error"]["code"])
        self.baselines.fail = None

        self.versions.fail = "CAPABILITY_EVIDENCE_UNAVAILABLE"
        response = self.client.post(
            self.baseline_path + "/versions", headers=self.headers,
            json={"items": [self.item]},
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("CAPABILITY_EVIDENCE_REQUIRED", response.json()["error"]["code"])
        self.versions.fail = None

        self.states.fail = "CONFLICT_VERSION"
        response = self.client.patch(
            self.baseline_path, headers=self.headers, json={"name": "New"},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("CONFLICT_VERSION", response.json()["error"]["code"])
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
