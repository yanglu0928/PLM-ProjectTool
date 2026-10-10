from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityItemView, CapabilityReadError,
    CapabilityReadQuery, CapabilityReadService, CapabilityVersionView,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
USER = uuid.uuid4()
BASELINE = uuid.uuid4()
VERSION = uuid.uuid4()
SESSION = b"s" * 32


class _Tx(AbstractContextManager):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _SessionAccess:
    user_id = USER

    def authenticated_user(self, transaction, *, session_token, now):
        return self.user_id


class _CurrentUser:
    role = "DEPLOYMENT_ADMIN"

    def current_enabled_user(self, transaction, *, user_id):
        return CurrentUserFacts(user_id, self.role)


class _Membership:
    allowed = True
    calls = 0

    def has_active_membership(self, transaction, *, user_id):
        self.calls += 1
        return self.allowed


class _Guard:
    error = False

    def require_valid(self, *, trace_id):
        if self.error:
            raise RuntimeLicenseError("TRUST_STATE_INVALID")
        return object()


def _baseline(number: int) -> CapabilityBaselineView:
    identity = uuid.UUID(int=number)
    return CapabilityBaselineView(
        identity, f"CAP-{number}", "name", None, "ACTIVE",
        "sha256:" + "a" * 64, VERSION, NOW, NOW, '"v1"',
    )


def _version(number: int) -> CapabilityVersionView:
    return CapabilityVersionView(
        uuid.UUID(int=number), BASELINE, number, "APPROVED",
        "sha256:" + "b" * 64, "c" * 64, 1, 1, 1, None,
        uuid.uuid4(), uuid.uuid4(), NOW,
    )


def _item(number: int) -> CapabilityItemView:
    return CapabilityItemView(
        uuid.UUID(int=number + 1), VERSION, BASELINE, number,
        f"CAP.{number}", "domain", "module", "feature", "name",
        "description", "boundary", (), (), "AVAILABLE",
        (uuid.uuid4(),), (uuid.uuid4(),),
    )


class _Repository:
    visibility = None
    rows = ()

    def _capture(self, visibility):
        self.visibility = visibility
        return self.rows

    def list_baselines(self, transaction, *, visibility, after_id, limit):
        self.limit, self.after = limit, after_id
        return self._capture(visibility)

    def get_baseline(self, transaction, *, visibility, baseline_id):
        rows = self._capture(visibility)
        return rows[0] if rows else None

    def list_versions(self, transaction, *, visibility, baseline_id,
                      after_version_no, limit):
        self.limit, self.after = limit, after_version_no
        return self._capture(visibility)

    def get_version(self, transaction, *, visibility, baseline_id,
                    baseline_version_id):
        rows = self._capture(visibility)
        return rows[0] if rows else None

    def list_items(self, transaction, *, visibility, baseline_id,
                   baseline_version_id, after_ordinal, limit):
        self.limit, self.after = limit, after_ordinal
        return self._capture(visibility)


class CapabilityReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.session = _SessionAccess()
        self.user = _CurrentUser()
        self.membership = _Membership()
        self.membership.calls = 0
        self.guard = _Guard()
        self.guard.error = False
        self.repository = _Repository()
        self.repository.rows = ()
        self.service = CapabilityReadService(
            unit_of_work=_Tx, session_access=self.session,
            current_user=self.user, membership=self.membership,
            license_guard=self.guard, repository=self.repository,
            clock=lambda: NOW,
        )
        self.query = CapabilityReadQuery(SESSION, uuid.uuid4())

    def test_admin_reads_history_without_membership(self):
        self.repository.rows = (_baseline(1), _baseline(2))
        page = self.service.list_baselines(self.query, page_size=1)
        self.assertEqual("ADMIN_HISTORY", self.repository.visibility)
        self.assertEqual(0, self.membership.calls)
        self.assertTrue(page.has_more)
        self.assertEqual(uuid.UUID(int=1), page.next_position)
        self.assertEqual(2, self.repository.limit)

    def test_member_reads_current_approved_projection(self):
        self.user.role = "NONE"
        self.repository.rows = (_version(1),)
        item = self.service.get_version(
            self.query, baseline_id=BASELINE, baseline_version_id=VERSION,
        )
        self.assertEqual(1, item.version_no)
        self.assertEqual("CURRENT_APPROVED", self.repository.visibility)
        self.assertEqual(1, self.membership.calls)

    def test_nonmember_is_denied_before_repository(self):
        self.user.role = "NONE"
        self.membership.allowed = False
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(self.query, page_size=20)
        self.assertEqual("AUTH_ACCESS_DENIED", raised.exception.code)
        self.assertIsNone(self.repository.visibility)

    def test_invalid_session_and_disabled_user_fail_closed(self):
        self.session.user_id = None
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(self.query, page_size=20)
        self.assertEqual("AUTH_ACCESS_DENIED", raised.exception.code)
        self.session.user_id = USER
        self.user.current_enabled_user = lambda *args, **kwargs: None
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(self.query, page_size=20)
        self.assertEqual("AUTH_ACCESS_DENIED", raised.exception.code)

    def test_license_error_is_safely_mapped(self):
        self.guard.error = True
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(self.query, page_size=20)
        self.assertEqual("LICENSE_OPERATION_DENIED", raised.exception.code)

    def test_missing_detail_is_not_found(self):
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.get_baseline(self.query, BASELINE)
        self.assertEqual("RESOURCE_NOT_FOUND", raised.exception.code)

    def test_version_descending_and_item_ascending_positions(self):
        self.repository.rows = (_version(5), _version(4))
        versions = self.service.list_versions(
            self.query, baseline_id=BASELINE, page_size=1,
            after_version_no=6,
        )
        self.assertEqual(5, versions.next_position)
        self.repository.rows = (_item(0), _item(1))
        items = self.service.list_items(
            self.query, baseline_id=BASELINE, baseline_version_id=VERSION,
            page_size=1, after_ordinal=0,
        )
        self.assertEqual(0, items.next_position)

    def test_invalid_query_and_page_are_rejected_before_dependencies(self):
        for query, size in (
            (CapabilityReadQuery(b"short", uuid.uuid4()), 10),
            (self.query, 0), (self.query, 201),
        ):
            with self.subTest(query=query, size=size):
                with self.assertRaises(CapabilityReadError) as raised:
                    self.service.list_baselines(query, page_size=size)
                self.assertEqual("VALIDATION_FAILED", raised.exception.code)

    def test_repository_shape_violation_is_unavailable(self):
        self.repository.rows = [_baseline(1)]
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(self.query, page_size=20)
        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)

    def test_cursor_visibility_is_rechecked_in_owner_transaction(self):
        self.repository.rows = (_baseline(1),)
        with self.assertRaises(CapabilityReadError) as raised:
            self.service.list_baselines(
                CapabilityReadQuery(SESSION, uuid.uuid4(), "CURRENT_APPROVED"),
                page_size=20,
            )
        self.assertEqual("VALIDATION_FAILED", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
