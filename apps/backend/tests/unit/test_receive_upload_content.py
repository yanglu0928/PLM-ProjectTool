from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from contextlib import contextmanager

from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, ReceiveUploadContentService, UploadContentError, UploadContentIntent,
)
from plm_assistant.modules.document.infrastructure.content_spool import StagedContentProof
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


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

    def test_replay_body_must_match_declared_bytes(self):
        body = b"%PDF-1.7\nsynthetic\n%%EOF\n"
        ReceiveUploadContentService._validate_replay_body([body[:4], body[4:]], self.command)
        for chunks, code in (
            ([], "FILE_INTEGRITY_MISMATCH"),
            ([body[:-1] + b"!"], "FILE_INTEGRITY_MISMATCH"),
            ([body, b"extra"], "FILE_TOO_LARGE"),
            (["not bytes"], "VALIDATION_FAILED"),
            ([b"x" * 1_048_577], "VALIDATION_FAILED"),
        ):
            with self.subTest(code=code, chunks=len(chunks)), self.assertRaises(UploadContentError) as raised:
                ReceiveUploadContentService._validate_replay_body(chunks, self.command)
            self.assertEqual(raised.exception.code, code)

    def test_license_is_rechecked_after_stream_before_stage(self):
        class Guard:
            calls = 0

            def require_valid(self, *, trace_id):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeLicenseError("EXPIRED")

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Access:
            def require_in_transaction(self, *_args, **_kwargs):
                return None

        class Repository:
            staged = False

            def preflight(self, *_args, **_kwargs):
                return UploadContentIntent("report.pdf", None, None)

            def stage(self, *_args, **_kwargs):
                self.staged = True
                return uuid.uuid4()

        class Spool:
            @contextmanager
            def recover_existing(self, **_kwargs):
                yield None

            def receive(self, *, chunks, **kwargs):
                assert b"".join(chunks)
                return StagedContentProof("temp/global/objects/aa/" + uuid.uuid4().hex,
                                          self_sha, self_length, "application/pdf")

        class Storage:
            def verify_content(self, *_args, **_kwargs):
                return None

        self_sha, self_length = self.command.declared_sha256, self.command.declared_length
        guard, repository = Guard(), Repository()
        service = ReceiveUploadContentService(
            unit_of_work=Transaction, access=Access(), repository=repository,
            audit=object(), spool=Spool(), storage=Storage(), license_guard=guard,
        )
        with self.assertRaises(RuntimeLicenseError):
            service.receive(self.command, chunks=[b"%PDF-1.7\nsynthetic\n%%EOF\n"])
        self.assertEqual(guard.calls, 2)
        self.assertFalse(repository.staged)


if __name__ == "__main__":
    unittest.main()
