from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.ai.application.provider_metadata import (
    AIProviderMetadataError, AIProviderMetadataQuery, AIProviderMetadataService,
    AIProviderMetadataView,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind


class AIProviderMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = AIProviderMetadataQuery(b"s" * 32, uuid.uuid4())
        self.service = AIProviderMetadataService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            repository=object(),
        )

    def test_bad_query_is_rejected_before_io(self) -> None:
        for change in ({"session_token": b"short"}, {"trace_id": uuid.UUID(int=0)}):
            with self.subTest(change=change), self.assertRaises(AIProviderMetadataError) as caught:
                self.service.get(replace(self.query, **change), uuid.uuid4())
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(AIProviderMetadataError) as caught:
            self.service.get(self.query, uuid.UUID(int=0))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_view_has_strong_resource_etag_and_no_secret_ref_field(self) -> None:
        view = AIProviderMetadataView(
            uuid.uuid4(), ProviderKind.CUSTOM, "Synthetic", "endpoint.synthetic",
            "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
            frozenset({ProviderCapability.CHAT}), "****12345678", "CONFIGURED", 2, 7,
        )
        self.assertEqual(view.etag, '"v7"')
        self.assertFalse(hasattr(view, "secret_ref"))
        self.assertNotIn("s" * 32, repr(self.query))

    def test_list_requires_dedicated_cursor_key_and_bounded_page(self) -> None:
        with self.assertRaises(ValueError):
            ProviderListCursorCodec(b"short")
        with self.assertRaises(AIProviderMetadataError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_UNAVAILABLE")
        for size in (0, 201, True):
            with self.subTest(size=size), self.assertRaises(AIProviderMetadataError) as caught:
                self.service.list_page(self.query, page_size=size)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_cursor_binds_family_session_size_and_position(self) -> None:
        codec = ProviderListCursorCodec(b"k" * 32)
        position = datetime(2026, 10, 2, tzinfo=timezone.utc)
        provider_id = uuid.uuid4()
        token = codec.encode(session_token=b"s" * 32, page_size=2,
                             created_at=position, provider_id=provider_id)
        self.assertEqual(codec.decode(token, session_token=b"s" * 32, page_size=2),
                         (position, provider_id))
        for changed in (token[:-1] + ("A" if token[-1] != "A" else "B"), "garbage"):
            with self.assertRaises(ValueError):
                codec.decode(changed, session_token=b"s" * 32, page_size=2)
        with self.assertRaises(ValueError):
            codec.decode(token, session_token=b"x" * 32, page_size=2)
        with self.assertRaises(ValueError):
            codec.decode(token, session_token=b"s" * 32, page_size=3)
        with self.assertRaises(ValueError):
            ProviderListCursorCodec(b"z" * 32).decode(
                token, session_token=b"s" * 32, page_size=2,
            )


if __name__ == "__main__":
    unittest.main()
