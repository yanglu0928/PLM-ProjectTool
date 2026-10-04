from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.capability.api.read import create_capability_read_router
from plm_assistant.modules.capability.api.read_cursor import (
    CapabilityBaselineCursorCodec, CapabilityChildCursorCodec,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselinePage, CapabilityBaselineView, CapabilityItemPage,
    CapabilityItemView, CapabilityReadError, CapabilityVersionPage,
    CapabilityVersionView,
)


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
BASELINE, VERSION, ITEM = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
DOCUMENT, EVIDENCE = uuid.uuid4(), uuid.uuid4()


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"a" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


BASELINE_VIEW = CapabilityBaselineView(
    BASELINE, "CAP-001", "Standard", None, "ACTIVE",
    "sha256:" + "a" * 64, VERSION, NOW, NOW, '"v2"',
)
VERSION_VIEW = CapabilityVersionView(
    VERSION, BASELINE, 1, "APPROVED", "sha256:" + "a" * 64,
    "b" * 64, 1, 1, 1, None, uuid.uuid4(), uuid.uuid4(), NOW,
)
ITEM_VIEW = CapabilityItemView(
    ITEM, VERSION, BASELINE, 0, "CAP.ITEM", "domain", "module", "feature",
    "Item", "Description", "Boundary", ("pre",), ("IF-1",), "AVAILABLE",
    (DOCUMENT,), (EVIDENCE,),
)


class Reads:
    fail = None

    def _check(self, query):
        self.query = query
        if self.fail:
            raise CapabilityReadError(self.fail)
        return query.expected_visibility or "ADMIN_HISTORY"

    def list_baselines(self, query, *, page_size, after_id=None):
        visibility = self._check(query)
        self.after, self.page_size = after_id, page_size
        more = query.expected_visibility is None
        return CapabilityBaselinePage(
            (BASELINE_VIEW,), BASELINE if more else None, more, visibility,
        )

    def get_baseline(self, query, baseline_id):
        self._check(query)
        self.baseline_id = baseline_id
        return BASELINE_VIEW

    def list_versions(self, query, *, baseline_id, page_size,
                      after_version_no=None):
        visibility = self._check(query)
        self.baseline_id, self.after = baseline_id, after_version_no
        return CapabilityVersionPage((VERSION_VIEW,), None, False, visibility)

    def get_version(self, query, *, baseline_id, baseline_version_id):
        self._check(query)
        self.baseline_id, self.version_id = baseline_id, baseline_version_id
        return VERSION_VIEW

    def list_items(self, query, *, baseline_id, baseline_version_id,
                   page_size, after_ordinal=None):
        visibility = self._check(query)
        self.baseline_id, self.version_id = baseline_id, baseline_version_id
        self.after = after_ordinal
        return CapabilityItemPage((ITEM_VIEW,), None, False, visibility)


class CapabilityReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.reads.fail = None
        router = create_capability_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads,
            baseline_cursors=CapabilityBaselineCursorCodec(b"b" * 32),
            child_cursors=CapabilityChildCursorCodec(b"c" * 32),
        )
        self.client = TestClient(
            create_app(capability_read_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"a" * 32).hex()}
        self.root = "/api/v1/global/capability-baselines"

    def test_default_closed_and_baseline_cursor_rechecks_visibility(self):
        paths = (
            self.root, f"{self.root}/{BASELINE}",
            f"{self.root}/{BASELINE}/versions",
            f"{self.root}/{BASELINE}/versions/{VERSION}",
            f"{self.root}/{BASELINE}/versions/{VERSION}/items",
        )
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for path in paths:
                with self.subTest(path=path):
                    self.assertEqual(404, bare.get(path).status_code)
        first = self.client.get(
            self.root + "?page_size=1", headers=self.headers,
        )
        self.assertEqual(200, first.status_code)
        self.assertTrue(first.json()["data"]["has_more"])
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}", headers=self.headers,
        )
        self.assertEqual(200, second.status_code)
        self.assertEqual("ADMIN_HISTORY", self.reads.query.expected_visibility)
        self.assertEqual(BASELINE, self.reads.after)

    def test_five_safe_read_projections(self):
        baseline = self.client.get(f"{self.root}/{BASELINE}", headers=self.headers)
        versions = self.client.get(
            f"{self.root}/{BASELINE}/versions", headers=self.headers,
        )
        version = self.client.get(
            f"{self.root}/{BASELINE}/versions/{VERSION}", headers=self.headers,
        )
        items = self.client.get(
            f"{self.root}/{BASELINE}/versions/{VERSION}/items", headers=self.headers,
        )
        self.assertEqual(200, baseline.status_code)
        self.assertEqual('"v2"', baseline.headers["etag"])
        self.assertEqual(str(BASELINE), baseline.json()["data"]["baseline_id"])
        self.assertEqual(200, versions.status_code)
        self.assertEqual(str(VERSION), versions.json()["data"]["items"][0][
            "baseline_version_id"])
        self.assertEqual(200, version.status_code)
        self.assertEqual("APPROVED", version.json()["data"]["state"])
        self.assertEqual(200, items.status_code)
        self.assertEqual(str(ITEM), items.json()["data"]["items"][0][
            "capability_item_id"])
        self.assertNotIn("query", items.text.lower())

    def test_strict_query_path_session_and_host(self):
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1", headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.get(
            self.root + "?page_size=0", headers=self.headers,
        ).status_code)
        self.assertEqual(400, self.client.get(
            f"{self.root}/{BASELINE}?extra=1", headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.get(
            f"{self.root}/{str(BASELINE).upper()}", headers=self.headers,
        ).status_code)
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.headers, "host": "evil.test"},
        ).status_code)

    def test_safe_error_mapping(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404),
            ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("VALIDATION_FAILED", 422),
            ("CAPABILITY_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.fail = code
                response = self.client.get(self.root, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
