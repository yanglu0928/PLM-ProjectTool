from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.api.global_capability_cursor import (
    GlobalCapabilityFixedItemsCursorCodec,
)


class GlobalCapabilityFixedItemsCursorTests(unittest.TestCase):
    def test_bound_context_and_tampering(self):
        codec = GlobalCapabilityFixedItemsCursorCodec(b"k" * 32)
        review, version, session = uuid.uuid4(), uuid.uuid4(), b"s" * 32
        token = codec.encode(
            review_id=review, version_id=version, session_token=session,
            page_size=1, after_ordinal=0,
        )
        self.assertEqual(codec.decode(
            token, review_id=review, version_id=version,
            session_token=session, page_size=1,
        ), 0)
        for value, changed in (
            (token, {"review_id": uuid.uuid4()}),
            (token, {"version_id": uuid.uuid4()}),
            (token, {"session_token": b"t" * 32}),
            (token, {"page_size": 2}),
            (token[:-1] + ("A" if token[-1] != "A" else "B"), {}),
        ):
            with self.subTest(changed=changed), self.assertRaises(ApplicationError):
                codec.decode(value, **{
                    "review_id": review, "version_id": version,
                    "session_token": session, "page_size": 1, **changed,
                })

    def test_invalid_key_and_position_fail_closed(self):
        with self.assertRaises(ValueError):
            GlobalCapabilityFixedItemsCursorCodec(b"short")
        codec = GlobalCapabilityFixedItemsCursorCodec(b"k" * 32)
        with self.assertRaises(ValueError):
            codec.encode(review_id=uuid.uuid4(), version_id=uuid.uuid4(),
                         session_token=b"s" * 32, page_size=51, after_ordinal=0)


if __name__ == "__main__":
    unittest.main()
