from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError


class EvidenceListCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = EvidenceListCursorCodec(b"e" * 32)
        self.project = uuid.uuid4()
        self.evidence = uuid.uuid4()
        self.created = datetime(2026, 10, 1, 1, 2, 3, 123456,
                                tzinfo=timezone(timedelta(hours=8)))
        self.args = dict(session_token=b"s" * 32, scope="PROJECT",
                         project_id=self.project, page_size=25)

    def test_roundtrip_preserves_utc_microsecond_and_identity(self):
        token = self.codec.encode(**self.args, created_at=self.created,
                                  evidence_id=self.evidence)
        created, evidence = self.codec.decode(token, **self.args)
        self.assertEqual(created, self.created.astimezone(timezone.utc))
        self.assertEqual(evidence, self.evidence)
        self.assertNotIn(str(self.project), token)
        self.assertNotIn("synthetic", token)

    def test_session_scope_project_size_and_key_are_bound(self):
        token = self.codec.encode(**self.args, created_at=self.created,
                                  evidence_id=self.evidence)
        variants = (
            {**self.args, "session_token": b"x" * 32},
            {**self.args, "project_id": uuid.uuid4()},
            {**self.args, "page_size": 26},
            {**self.args, "scope": "GLOBAL", "project_id": None},
        )
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ApplicationError):
                self.codec.decode(token, **variant)
        with self.assertRaises(ApplicationError):
            EvidenceListCursorCodec(b"x" * 32).decode(token, **self.args)

    def test_tamper_noncanonical_and_bad_positions_rejected(self):
        token = self.codec.encode(**self.args, created_at=self.created,
                                  evidence_id=self.evidence)
        for bad in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                    token + "=", "not-a-cursor", "", 4):
            with self.subTest(bad=bad), self.assertRaises(ApplicationError):
                self.codec.decode(bad, **self.args)
        for bad in (datetime(2026, 10, 1), "2026-10-01", None):
            with self.subTest(created_at=bad), self.assertRaises(ValueError):
                self.codec.encode(**self.args, created_at=bad,
                                  evidence_id=self.evidence)
        with self.assertRaises(ValueError):
            self.codec.encode(**self.args, created_at=self.created,
                              evidence_id=uuid.UUID(int=0))
        with self.assertRaises(ValueError):
            EvidenceListCursorCodec(b"short")


if __name__ == "__main__":
    unittest.main()
