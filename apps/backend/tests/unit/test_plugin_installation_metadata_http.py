from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.plugin.api.installation_metadata import (
    create_plugin_installation_metadata_router,
)
from plm_assistant.modules.plugin.application.installation_metadata import (
    PluginInstallationMetadataView,
    PluginOperationMetadata,
)


class _Sessions:
    def validate(self, _token: bytes):
        return object()


class _Installations:
    def __init__(self):
        self.installation_id = uuid.uuid4()
        self.view = PluginInstallationMetadataView(
            plugin_installation_id=self.installation_id,
            plugin_package_id=uuid.uuid4(),
            plugin_id="synthetic.read",
            plugin_name="Synthetic Plugin",
            plugin_version="1.0.0",
            package_sha256="a" * 64,
            package_state="VERIFIED",
            plugin_api_version="1.0.0",
            supported_os=("windows-11",),
            architecture="x86_64",
            operations=(PluginOperationMetadata("document.render", ("DOCX",), "1.0.0"),),
            installation_state="ENABLED",
            compatibility_state="COMPATIBLE",
            runtime_snapshot={
                "schema_version": "1", "os": "windows-11",
                "architecture": "x86_64", "python_version": "3.13.17",
                "dependency_versions": {},
            },
            enabled_operations=("document.render",),
            lock_version=7,
        )
        self.query = None
    def get(self, query, installation_id):
        self.query = query
        if installation_id != self.installation_id:
            raise AssertionError("wrong installation identity")
        return self.view


class PluginInstallationMetadataHttpTests(unittest.TestCase):
    def setUp(self):
        self.installations = _Installations()
        router = create_plugin_installation_metadata_router(
            sessions=_Sessions(),
            origins=LoginOriginPolicy(["https://plm.example"]),
            installations=self.installations,
        )
        self.client = TestClient(create_app(plugin_installation_metadata_router=router))
        self.headers = {
            "Host": "plm.example",
            "Cookie": "plm_session=" + ("ab" * 32),
        }

    def test_detail_returns_safe_projection_etag_and_no_store(self):
        response = self.client.get(
            f"/api/v1/admin/plugins/installations/{self.installations.installation_id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(body["etag"], '"v7"')
        self.assertEqual(response.headers["etag"], '"v7"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(body["enabled_operations"], ["document.render"])
        self.assertNotIn("signature", body)
        self.assertNotIn("runtime_path", body)
        self.assertEqual(len(self.installations.query.session_token), 32)

    def test_detail_rejects_query_parameters(self):
        response = self.client.get(
            f"/api/v1/admin/plugins/installations/{self.installations.installation_id}?debug=1",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
