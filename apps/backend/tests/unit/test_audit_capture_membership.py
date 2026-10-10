import hashlib
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

from plm_assistant.modules.audit.domain.capture_membership import (
    CaptureMember, digest_members, MEMBERSHIP_VERSION,
)


class CaptureMembershipTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 26, 1, 2, 3, 456789, timezone.utc)
        self.first = CaptureMember(UUID(int=2), self.now)
        self.second = CaptureMember(UUID(int=1), self.now)

    def test_explicit_empty_domain_vector(self):
        result = digest_members(iter(()))
        self.assertEqual(result.count, 0)
        self.assertEqual(result.version, MEMBERSHIP_VERSION)
        self.assertEqual(result.sha256, hashlib.sha256(
            b"PLM-AUDIT-CAPTURE-MEMBERSHIP-V1\x00").hexdigest())
        self.assertNotEqual(result.sha256, hashlib.sha256(b"").hexdigest())

    def test_canonical_vector_and_generator(self):
        result = digest_members(x for x in (self.first, self.second))
        expected = (b"PLM-AUDIT-CAPTURE-MEMBERSHIP-V1\x00"
            b"00000000-0000-0000-0000-000000000002|2026-09-26T01:02:03.456789Z\n"
            b"00000000-0000-0000-0000-000000000001|2026-09-26T01:02:03.456789Z\n")
        self.assertEqual(result.sha256, hashlib.sha256(expected).hexdigest())
        self.assertEqual(result.count, 2)

    def test_equivalent_timezone(self):
        local = self.now.astimezone(timezone(timedelta(hours=8)))
        self.assertEqual(digest_members([self.first]),
            digest_members([CaptureMember(self.first.event_id, local)]))

    def test_timestamp_and_uuid_are_bound(self):
        original = digest_members([self.first]).sha256
        for changed in (CaptureMember(UUID(int=3), self.now),
                CaptureMember(self.first.event_id, self.now - timedelta(microseconds=1))):
            self.assertNotEqual(original, digest_members([changed]).sha256)

    def test_order_and_duplicate_identifiers(self):
        for members in ([self.second, self.first], [self.first, self.first],
                [self.first, CaptureMember(self.first.event_id, self.now - timedelta(seconds=1))],
                [self.first, CaptureMember(UUID(int=3), self.now + timedelta(seconds=1))]):
            with self.subTest(members=members), self.assertRaises(ValueError):
                digest_members(members)

    def test_invalid_coordinates_and_types(self):
        for event_id, stamp in ((UUID(int=0), self.now), (True, self.now),
                (str(self.first.event_id), self.now), (self.first.event_id, self.now.replace(tzinfo=None)),
                (self.first.event_id, "2026-09-26")):
            with self.subTest(event_id=event_id, stamp=stamp), self.assertRaises(ValueError):
                CaptureMember(event_id, stamp)
        with self.assertRaises(ValueError):
            digest_members([object()])

    def test_frozen_and_corruption_revalidated(self):
        with self.assertRaises(FrozenInstanceError):
            self.first.event_id = UUID(int=3)
        object.__setattr__(self.first, "event_id", UUID(int=0))
        with self.assertRaises(ValueError):
            digest_members([self.first])

    def test_source_exception_is_not_truncated_success(self):
        def broken():
            yield self.first
            raise RuntimeError("source unavailable")
        with self.assertRaises(RuntimeError):
            digest_members(broken())
