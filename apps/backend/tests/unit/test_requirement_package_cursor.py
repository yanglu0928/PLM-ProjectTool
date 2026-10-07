from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.api.package_cursor import (
    RequirementPackageCursorCodec,
)


class RequirementPackageCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = RequirementPackageCursorCodec(b"p" * 32)
        self.project, self.package = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32
        self.updated_at = datetime(2026, 10, 8, tzinfo=timezone.utc)

    def token(self):
        return self.codec.encode(
            project_id=self.project, session_token=self.session, page_size=25,
            updated_at=self.updated_at, package_id=self.package)

    def test_round_trip_complete_pair(self):
        self.assertEqual(
            (self.updated_at, self.package), self.codec.decode(
                self.token(), project_id=self.project,
                session_token=self.session, page_size=25))

    def test_context_and_signature_are_bound(self):
        token = self.token()
        for project, session, size, candidate in (
            (uuid.uuid4(), self.session, 25, token),
            (self.project, b"x" * 32, 25, token),
            (self.project, self.session, 24, token),
            (self.project, self.session, 25, token[:-1] + "A"),
        ):
            with self.subTest(project=project, size=size), self.assertRaises(
                    ApplicationError) as caught:
                self.codec.decode(candidate, project_id=project,
                                  session_token=session, page_size=size)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_dedicated_key_and_position_are_strict(self):
        for key in (b"short", bytearray(b"p" * 32)):
            with self.assertRaises(ValueError):
                RequirementPackageCursorCodec(key)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.codec.encode(
                project_id=self.project, session_token=self.session,
                page_size=0, updated_at=self.updated_at, package_id=self.package)


if __name__ == "__main__":
    unittest.main()
