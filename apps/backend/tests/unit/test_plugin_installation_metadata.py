from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.plugin.application.installation_metadata import (
    PluginInstallationMetadataError,
    PluginInstallationMetadataQuery,
    PluginInstallationMetadataService,
    PluginInstallationMetadataView,
    PluginOperationMetadata,
)


class _Uow:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class _Access:
    def __init__(self, actor=None): self.actor = actor or uuid.uuid4(); self.calls = 0
    def authorized_admin(self, _tx, *, session_token, now):
        self.calls += 1
        return self.actor


class _License:
    def __init__(self, fail=False): self.fail = fail; self.calls = 0
    def require_valid(self, *, trace_id):
        self.calls += 1
        if self.fail:
            raise RuntimeError("denied")


class _Repository:
    def __init__(self, view): self.view = view; self.requested = []
    def get(self, _tx, *, installation_id):
        self.requested.append(installation_id)
        return self.view


def _view(installation_id: uuid.UUID) -> PluginInstallationMetadataView:
    return PluginInstallationMetadataView(
        plugin_installation_id=installation_id,
        plugin_package_id=uuid.uuid4(),
        plugin_id="synthetic.read",
        plugin_name="测试插件",
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


class PluginInstallationMetadataTests(unittest.TestCase):
    def setUp(self):
        self.installation_id = uuid.uuid4()
        self.access = _Access()
        self.license = _License()
        self.repository = _Repository(_view(self.installation_id))
        self.service = PluginInstallationMetadataService(
            unit_of_work=_Uow, access=self.access, license_guard=self.license,
            repository=self.repository,
            clock=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc),
        )
        self.query = PluginInstallationMetadataQuery(b"s" * 32, uuid.uuid4())

    def test_get_returns_exact_version_and_safe_package_projection(self):
        result = self.service.get(self.query, self.installation_id)
        self.assertEqual(result.etag, '"v7"')
        self.assertEqual(result.enabled_operations, ("document.render",))
        self.assertEqual(result.package_sha256, "a" * 64)
        self.assertEqual(self.access.calls, 2)
        self.assertEqual(self.license.calls, 1)

    def test_missing_installation_is_not_found(self):
        self.repository.view = None
        with self.assertRaises(PluginInstallationMetadataError) as caught:
            self.service.get(self.query, self.installation_id)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_invalid_projection_fails_closed(self):
        self.repository.view = _view(uuid.uuid4())
        with self.assertRaises(PluginInstallationMetadataError) as caught:
            self.service.get(self.query, self.installation_id)
        self.assertEqual(caught.exception.code, "PLUGIN_INSTALLATION_UNAVAILABLE")

    def test_invalid_query_performs_no_io(self):
        for query in (
            PluginInstallationMetadataQuery(b"short", self.query.trace_id),
            PluginInstallationMetadataQuery(self.query.session_token, uuid.UUID(int=0)),
        ):
            with self.assertRaises(PluginInstallationMetadataError) as caught:
                self.service.get(query, self.installation_id)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.access.calls, 0)
        self.assertEqual(self.repository.requested, [])

    def test_session_and_license_are_required(self):
        self.access.actor = None
        with self.assertRaises(PluginInstallationMetadataError) as caught:
            self.service.get(self.query, self.installation_id)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.access.actor = uuid.uuid4()
        self.license.fail = True
        with self.assertRaises(PluginInstallationMetadataError) as caught:
            self.service.get(self.query, self.installation_id)
        self.assertEqual(caught.exception.code, "PLUGIN_INSTALLATION_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
