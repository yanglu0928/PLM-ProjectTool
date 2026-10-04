from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.capability.api.read_cursor import (
    CapabilityBaselineCursorCodec, CapabilityChildCursorCodec,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


class CapabilityReadCursorTests(unittest.TestCase):
    def setUp(self):
        self.session = b"s" * 32
        self.scope = uuid.uuid4()
        self.baseline = CapabilityBaselineCursorCodec(b"b" * 32)
        self.child = CapabilityChildCursorCodec(b"c" * 32)

    def test_baseline_round_trip_and_all_bindings(self):
        position = uuid.uuid4()
        token = self.baseline.encode(
            session_token=self.session, page_size=25,
            visibility="ADMIN_HISTORY", baseline_id=position,
        )
        self.assertEqual(position, self.baseline.decode(
            token, session_token=self.session, page_size=25,
            visibility="ADMIN_HISTORY",
        ))
        for kwargs in (
            {"session_token": b"x" * 32, "page_size": 25,
             "visibility": "ADMIN_HISTORY"},
            {"session_token": self.session, "page_size": 24,
             "visibility": "ADMIN_HISTORY"},
            {"session_token": self.session, "page_size": 25,
             "visibility": "CURRENT_APPROVED"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ApplicationError):
                self.baseline.decode(token, **kwargs)

    def test_child_round_trip_and_resource_family_isolation(self):
        token = self.child.encode(
            family="capability-versions", scope_id=self.scope,
            session_token=self.session, page_size=10,
            visibility="CURRENT_APPROVED", position=9,
        )
        self.assertEqual(9, self.child.decode(
            token, family="capability-versions", scope_id=self.scope,
            session_token=self.session, page_size=10,
            visibility="CURRENT_APPROVED",
        ))
        for family, scope in (
            ("capability-items", self.scope),
            ("capability-versions", uuid.uuid4()),
        ):
            with self.subTest(family=family), self.assertRaises(ApplicationError):
                self.child.decode(
                    token, family=family, scope_id=scope,
                    session_token=self.session, page_size=10,
                    visibility="CURRENT_APPROVED",
                )

    def test_item_zero_position_is_valid_and_tampering_fails(self):
        token = self.child.encode(
            family="capability-items", scope_id=self.scope,
            session_token=self.session, page_size=1,
            visibility="ADMIN_HISTORY", position=0,
        )
        self.assertEqual(0, self.child.decode(
            token, family="capability-items", scope_id=self.scope,
            session_token=self.session, page_size=1,
            visibility="ADMIN_HISTORY",
        ))
        damaged = ("A" if token[0] != "A" else "B") + token[1:]
        with self.assertRaises(ApplicationError) as raised:
            self.child.decode(
                damaged, family="capability-items", scope_id=self.scope,
                session_token=self.session, page_size=1,
                visibility="ADMIN_HISTORY",
            )
        self.assertEqual("REQUEST_MALFORMED", raised.exception.spec.code)

    def test_keys_and_positions_are_strict(self):
        for codec in (CapabilityBaselineCursorCodec, CapabilityChildCursorCodec):
            with self.subTest(codec=codec), self.assertRaises(ValueError):
                codec(b"short")
        with self.assertRaises(ValueError):
            self.child.encode(
                family="capability-versions", scope_id=self.scope,
                session_token=self.session, page_size=10,
                visibility="ADMIN_HISTORY", position=0,
            )


if __name__ == "__main__":
    unittest.main()
