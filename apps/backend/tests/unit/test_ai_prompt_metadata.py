from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.prompt_metadata import (
    PromptMetadataError, PromptMetadataQuery, PromptMetadataService, PromptMetadataView,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Access:
    enabled = True

    def authorized_admin(self, transaction, *, session_token, now):
        return uuid.UUID(int=1) if self.enabled else None


class _Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class _Repo:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    def get(self, transaction, *, template_id):
        self.calls += 1
        return next((item for item in self.items if item.template_id == template_id), None)

    def list_page(self, transaction, *, after, limit):
        self.calls += 1
        items = sorted(self.items, key=lambda item: (item.created_at, item.template_id),
                       reverse=True)
        if after is not None:
            items = [item for item in items if (item.created_at, item.template_id) < after]
        return items[:limit]


class PromptMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = PromptMetadataQuery(b"s" * 32, uuid.uuid4())
        self.access, self.guard = _Access(), _Guard()
        at = datetime(2026, 10, 2, tzinfo=timezone.utc)
        self.items = [PromptMetadataView(uuid.UUID(int=i), PromptTaskType.GAP_ANALYSIS,
                                         "DRAFT", None, None, None, None, None, None, None,
                                         0, at) for i in (1, 2, 3)]
        self.repo = _Repo(self.items)
        self.codec = PromptListCursorCodec(b"k" * 32)
        self.service = PromptMetadataService(unit_of_work=_Tx, access=self.access,
                                             license_guard=self.guard, repository=self.repo,
                                             cursors=self.codec)

    def test_cursor_is_dedicated_bound_and_canonical(self) -> None:
        with self.assertRaises(ValueError):
            PromptListCursorCodec(b"short")
        token = self.codec.encode(session_token=self.query.session_token, page_size=2,
                                  created_at=self.items[0].created_at,
                                  template_id=self.items[0].template_id)
        self.assertEqual(self.codec.decode(token, session_token=b"s" * 32, page_size=2),
                         (self.items[0].created_at, self.items[0].template_id))
        for candidate in ("garbage", token[:-1] + ("A" if token[-1] != "A" else "B")):
            with self.assertRaises(ValueError):
                self.codec.decode(candidate, session_token=b"s" * 32, page_size=2)
        for session, size in ((b"x" * 32, 2), (b"s" * 32, 3)):
            with self.assertRaises(ValueError):
                self.codec.decode(token, session_token=session, page_size=size)
        with self.assertRaises(ValueError):
            PromptListCursorCodec(b"q" * 32).decode(
                token, session_token=b"s" * 32, page_size=2,
            )

    def test_keyset_page_and_detail(self) -> None:
        first = self.service.list_page(self.query, page_size=2)
        self.assertEqual([item.template_id.int for item in first.items], [3, 2])
        self.assertTrue(first.has_more)
        second = self.service.list_page(self.query, page_size=2, cursor=first.next_cursor)
        self.assertEqual([item.template_id.int for item in second.items], [1])
        self.assertFalse(second.has_more)
        self.assertEqual(self.service.get(self.query, uuid.UUID(int=2)).etag, '"v0"')
        self.assertNotIn("s" * 32, repr(self.query))
        self.assertFalse(hasattr(first.items[0], "system_template"))

    def test_validation_auth_license_and_missing(self) -> None:
        for query in (replace(self.query, session_token=b"short"),
                      replace(self.query, trace_id=uuid.UUID(int=0))):
            with self.assertRaises(PromptMetadataError) as caught:
                self.service.get(query, uuid.UUID(int=1))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        for size in (0, 201, True):
            with self.assertRaises(PromptMetadataError) as caught:
                self.service.list_page(self.query, page_size=size)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(PromptMetadataError) as caught:
            self.service.get(self.query, uuid.UUID(int=9))
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.access.enabled = False
        before = self.repo.calls
        with self.assertRaises(PromptMetadataError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repo.calls, before)
        self.access.enabled, self.guard.enabled = True, False
        with self.assertRaises(PromptMetadataError) as caught:
            self.service.get(self.query, uuid.UUID(int=1))
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.assertEqual(self.repo.calls, before)

    def test_cursor_failure_and_missing_key_fail_closed(self) -> None:
        with self.assertRaises(PromptMetadataError) as caught:
            self.service.list_page(self.query, cursor="tampered")
        self.assertEqual(caught.exception.code, "REQUEST_MALFORMED")
        no_key = PromptMetadataService(unit_of_work=_Tx, access=self.access,
                                       license_guard=self.guard, repository=self.repo)
        with self.assertRaises(PromptMetadataError) as caught:
            no_key.list_page(self.query)
        self.assertEqual(caught.exception.code, "AI_PROMPT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
