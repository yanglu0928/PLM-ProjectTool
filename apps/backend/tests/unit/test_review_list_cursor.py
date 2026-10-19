from __future__ import annotations

import base64
import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.api.list_cursor import ReviewListCursorCodec
from plm_assistant.modules.review.application.list_contract import ReviewListPosition


class ReviewListCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = ReviewListCursorCodec(b"r" * 32)
        self.session = b"s" * 32
        self.project = uuid.uuid4()
        self.position = ReviewListPosition(
            datetime(2026, 10, 19, 5, 30, 1, 123456,
                     tzinfo=timezone.utc), uuid.uuid4(),
        )
        self.token = self.codec.encode(
            session_token=self.session, project_id=self.project,
            view="my_pending", page_size=25, position=self.position,
        )

    def test_roundtrip_randomized_ciphertext_hides_position(self) -> None:
        self.assertEqual(self.codec.decode(
            self.token, session_token=self.session, project_id=self.project,
            view="my_pending", page_size=25,
        ), self.position)
        self.assertNotEqual(self.codec.encode(
            session_token=self.session, project_id=self.project,
            view="my_pending", page_size=25, position=self.position,
        ), self.token)
        encoded = self.token[3:]
        packed = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4))
        for secret in (
            str(self.position.review_id).encode("ascii"),
            self.position.created_at.isoformat().encode("ascii"),
            self.session, b"review_id", b"created_at",
        ):
            self.assertNotIn(secret, packed)

    def test_tamper_and_cross_context_fail_closed(self) -> None:
        cases = (
            (self.token[:-1] + ("A" if self.token[-1] != "A" else "B"),
             self.codec, self.session, self.project, "my_pending", 25),
            (self.token, ReviewListCursorCodec(b"x" * 32), self.session,
             self.project, "my_pending", 25),
            (self.token, self.codec, b"x" * 32, self.project,
             "my_pending", 25),
            (self.token, self.codec, self.session, uuid.uuid4(),
             "my_pending", 25),
            (self.token, self.codec, self.session, self.project, "all", 25),
            (self.token, self.codec, self.session, self.project,
             "my_pending", 50),
            ("not-a-cursor", self.codec, self.session, self.project,
             "my_pending", 25),
        )
        for token, codec, session, project, view, size in cases:
            with self.subTest(view=view, size=size), self.assertRaises(ApplicationError) as caught:
                codec.decode(token, session_token=session, project_id=project,
                             view=view, page_size=size)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_invalid_key_query_and_position_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReviewListCursorCodec(b"short")
        for session, project, view, size in (
            (b"short", self.project, "my_pending", 25),
            (self.session, uuid.UUID(int=0), "my_pending", 25),
            (self.session, self.project, "assigned", 25),
            (self.session, self.project, "my_pending", 201),
        ):
            with self.subTest(view=view, size=size), self.assertRaises(ValueError):
                self.codec.encode(
                    session_token=session, project_id=project, view=view,
                    page_size=size, position=self.position,
                )


if __name__ == "__main__":
    unittest.main()
