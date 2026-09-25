from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, ReceiveUploadContentService, UploadContentError,
)


class UploadContentValidationTests(unittest.TestCase):
    def setUp(self):
        body = b"%PDF-1.7\nsynthetic\n%%EOF\n"
        self.command = ReceiveUploadContent(
            uuid.uuid4(), "PROJECT", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "A" * 43, len(body), hashlib.sha256(body).digest(),
        )

    def test_identity_token_length_and_claims(self):
        ReceiveUploadContentService._validate(self.command)
        for change in (
            dict(upload_id=uuid.UUID(int=0)), dict(actor_id=uuid.UUID(int=0)),
            dict(scope="GLOBAL"), dict(project_id=None), dict(scope="OTHER"),
            dict(upload_token="short"), dict(upload_token="/" * 43),
            dict(declared_length=0), dict(declared_length=True),
            dict(declared_sha256=b"short"),
        ):
            with self.subTest(change=change), self.assertRaises(UploadContentError):
                ReceiveUploadContentService._validate(replace(self.command, **change))


if __name__ == "__main__":
    unittest.main()
