from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

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


if __name__ == "__main__":
    unittest.main()
