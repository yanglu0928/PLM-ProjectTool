from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.create_upload_intent import (
    CreateUploadIntent, CreateUploadIntentService, UploadIntentCreateError,
)
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer


class SyntheticProvider:
    def __init__(self, key=b"k" * 32):
        self.key = key

    def resolve_key(self, key_ref):
        return self.key if key_ref == "upload-test" else None


class UploadIntentCreateTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateUploadIntent(
            scope="PROJECT", project_id=uuid.uuid4(), actor_id=uuid.uuid4(),
            trace_id=uuid.uuid4(), purpose_code="PROJECT_RECORD",
            document_category="PROJECT_RECORD", title="Interview",
            original_display_name="interview.pdf", expected_size_bytes=100,
            mime_hint="application/pdf",
        )

    def test_validation_rejects_scope_shape_and_unsafe_metadata(self):
        worker = CreateUploadIntentService(
            unit_of_work=lambda: object(), access=object(), repository=object(),
            receipts=object(), audit=object(), token_issuer=object(),
        )
        worker._validate(self.command)
        for changes in (
            dict(scope="GLOBAL"), dict(project_id=None), dict(actor_id=uuid.UUID(int=0)),
            dict(purpose_code="bad"), dict(document_category="GENERATED_ARTIFACT"),
            dict(document_category="OTHER"), dict(title=" bad "),
            dict(original_display_name="bad\nname"), dict(expected_size_bytes=True),
            dict(expected_size_bytes=100_000_001),
            dict(target_document_id=uuid.uuid4()),
            dict(supersedes_version_id=uuid.uuid4()),
        ):
            with self.subTest(changes=changes), self.assertRaises(UploadIntentCreateError):
                worker._validate(replace(self.command, **changes))
        worker._validate(replace(self.command, target_document_id=uuid.uuid4(),
                                 document_category=None, title=None))
        worker._validate(replace(self.command, target_document_id=uuid.uuid4(),
                                 supersedes_version_id=uuid.uuid4(),
                                 document_category=None, title=None))
        with self.assertRaises(UploadIntentCreateError):
            worker._validate(replace(self.command, target_document_id=uuid.uuid4(),
                                     document_category=None, title=None,
                                     original_display_name=None))

    def test_token_is_deterministic_bound_and_unavailable_without_key(self):
        provider = SyntheticProvider()
        issuer = HmacUploadTokenIssuer(provider=provider, key_ref="upload-test")
        upload = uuid.uuid4()
        args = dict(upload_id=upload, actor_id=self.command.actor_id,
                    scope="PROJECT", project_id=self.command.project_id)
        token, digest = issuer.issue(**args)
        self.assertEqual((token, digest), issuer.issue(**args))
        self.assertEqual(digest, hashlib.sha256(token.encode("ascii")).digest())
        self.assertNotEqual(token, issuer.issue(**{**args, "actor_id": uuid.uuid4()})[0])
        self.assertNotEqual(token, issuer.issue(**{**args, "project_id": uuid.uuid4()})[0])
        self.assertNotIn(token, repr(issuer))
        provider.key = None
        with self.assertRaises(RuntimeError):
            issuer.issue(**args)


if __name__ == "__main__":
    unittest.main()
