from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.model_metadata import (
    AIModelMetadataError, AIModelMetadataQuery, AIModelMetadataService,
    AIModelMetadataView,
)
from plm_assistant.modules.ai.domain.model_definition import AIModelKind


class AIModelMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = AIModelMetadataQuery(b"s" * 32, uuid.uuid4())
        self.service = AIModelMetadataService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            repository=object(),
        )

    def test_bad_query_is_rejected_before_io(self) -> None:
        for change in ({"session_token": b"short"}, {"trace_id": uuid.UUID(int=0)}):
            with self.subTest(change=change), self.assertRaises(AIModelMetadataError) as caught:
                self.service.get(replace(self.query, **change), uuid.uuid4())
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(AIModelMetadataError) as caught:
            self.service.get(self.query, uuid.UUID(int=0))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_view_does_not_assert_quality_or_route(self) -> None:
        view = AIModelMetadataView(
            uuid.uuid4(), uuid.uuid4(), "embed-1", AIModelKind.EMBEDDING,
            "PROVIDER_MANAGED", 1024, False, 8192, ("quality.synthetic.v1",),
            "SUSPENDED", 7, datetime.now(timezone.utc),
        )
        self.assertEqual(view.etag, '"v7"')
        self.assertEqual(view.quality_status, "NOT_EVALUATED")
        self.assertFalse(hasattr(view, "secret_ref"))
        self.assertNotIn("s" * 32, repr(self.query))

    def test_cursor_is_dedicated_and_session_size_bound(self) -> None:
        with self.assertRaises(ValueError):
            ModelListCursorCodec(b"short")
        with self.assertRaises(AIModelMetadataError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "AI_MODEL_UNAVAILABLE")
        for size in (0, 201, True):
            with self.subTest(size=size), self.assertRaises(AIModelMetadataError) as caught:
                self.service.list_page(self.query, page_size=size)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        codec = ModelListCursorCodec(b"k" * 32)
        position, model_id = datetime(2026, 10, 2, tzinfo=timezone.utc), uuid.uuid4()
        token = codec.encode(session_token=b"s" * 32, page_size=2,
                             created_at=position, model_id=model_id)
        self.assertEqual(codec.decode(token, session_token=b"s" * 32, page_size=2),
                         (position, model_id))
        for changed in (token[:-1] + ("A" if token[-1] != "A" else "B"), "garbage"):
            with self.assertRaises(ValueError):
                codec.decode(changed, session_token=b"s" * 32, page_size=2)
        with self.assertRaises(ValueError):
            codec.decode(token, session_token=b"x" * 32, page_size=2)
        with self.assertRaises(ValueError):
            codec.decode(token, session_token=b"s" * 32, page_size=3)


if __name__ == "__main__":
    unittest.main()
