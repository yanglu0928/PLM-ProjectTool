from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.api.relation_cursor import (
    RequirementRelationCursorCodec,
)


class RequirementRelationCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = RequirementRelationCursorCodec(b"r" * 32)
        self.project, self.relation = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32

    def token(self):
        return self.codec.encode(
            project_id=self.project, session_token=self.session,
            page_size=25, relation_id=self.relation,
        )

    def test_round_trip_relation_id(self):
        self.assertEqual(self.relation, self.codec.decode(
            self.token(), project_id=self.project,
            session_token=self.session, page_size=25,
        ))

    def test_context_query_and_signature_are_bound(self):
        token = self.token()
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        for project, session, size, candidate in (
            (uuid.uuid4(), self.session, 25, token),
            (self.project, b"x" * 32, 25, token),
            (self.project, self.session, 24, token),
            (self.project, self.session, 25, tampered),
        ):
            with self.subTest(size=size), self.assertRaises(
                    ApplicationError) as caught:
                self.codec.decode(
                    candidate, project_id=project,
                    session_token=session, page_size=size,
                )
            self.assertEqual("REQUEST_MALFORMED", caught.exception.spec.code)

    def test_dedicated_key_and_position_are_strict(self):
        for key in (b"short", bytearray(b"r" * 32)):
            with self.assertRaises(ValueError):
                RequirementRelationCursorCodec(key)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.codec.encode(
                project_id=self.project, session_token=self.session,
                page_size=25, relation_id=uuid.UUID(int=0),
            )


if __name__ == "__main__":
    unittest.main()
