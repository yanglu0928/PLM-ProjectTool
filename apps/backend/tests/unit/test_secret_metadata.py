from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.secret_metadata import (
    SecretMetadataError, SecretMetadataQuery, SecretMetadataService,
    SecretMetadataView,
)


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Dependencies:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.guard_failure = False
        self.auth_calls = 0
        self.read_calls = 0
        self.view = SecretMetadataView(uuid.uuid4(), "AI_PROVIDER_KEY", "ACTIVE",
                                       "AI_PROVIDER_ADAPTER", 1, NOW, NOW)

    def uow(self):
        return Tx()

    def authorized_admin(self, tx, **_):
        self.auth_calls += 1
        return self.actor

    def require_valid(self, **_):
        if self.guard_failure:
            raise RuntimeError("expired license")
        return object()

    def get(self, tx, secret_id):
        self.read_calls += 1
        return self.view if secret_id == self.view.secret_id else None

    def list_page(self, tx, **kwargs):
        self.read_calls += 1
        return [self.view]


class SecretMetadataTests(unittest.TestCase):
    def setUp(self):
        self.deps = Dependencies()
        self.service = SecretMetadataService(
            unit_of_work=self.deps.uow, access=self.deps, license_guard=self.deps,
            repository=self.deps, clock=lambda: NOW,
        )
        self.query = SecretMetadataQuery(b"s" * 32, uuid.uuid4())

    def test_get_only_safe_metadata(self):
        result = self.service.get(self.query, self.deps.view.secret_id)
        self.assertEqual(result.current_version_no, 1)
        self.assertFalse(hasattr(result, "encrypted_payload"))
        self.assertEqual(self.deps.auth_calls, 2)

    def test_list_bounded(self):
        self.assertEqual(self.service.list_page(self.query, limit=1), [self.deps.view])
        with self.assertRaises(SecretMetadataError) as caught:
            self.service.list_page(self.query, limit=101)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_unauthorized_never_calls_repository(self):
        self.deps.actor = None
        with self.assertRaises(SecretMetadataError) as caught:
            self.service.get(self.query, self.deps.view.secret_id)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.deps.read_calls, 0)

    def test_license_failure_never_reads_metadata(self):
        self.deps.guard_failure = True
        with self.assertRaises(SecretMetadataError) as caught:
            self.service.get(self.query, self.deps.view.secret_id)
        self.assertEqual(caught.exception.code, "SECRET_UNAVAILABLE")
        self.assertEqual(self.deps.read_calls, 0)

    def test_missing_secret_classified(self):
        with self.assertRaises(SecretMetadataError) as caught:
            self.service.get(self.query, uuid.uuid4())
        self.assertEqual(caught.exception.code, "SECRET_NOT_FOUND")

    def test_invalid_request_rejected(self):
        with self.assertRaises(SecretMetadataError):
            self.service.get(SecretMetadataQuery(b"short", uuid.uuid4()), self.deps.view.secret_id)
        with self.assertRaises(SecretMetadataError):
            self.service.get(self.query, uuid.UUID(int=0))
        self.assertEqual(self.deps.read_calls, 0)


if __name__ == "__main__":
    unittest.main()
