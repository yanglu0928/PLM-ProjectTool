from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.audit.application.public import (
    AuditAccessDenied, AuditPage, AuditPosition, AuditQueryError,
    AuditQueryService, AuditSearch,
)


PROJECT_ID = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def search(**changes: object) -> AuditSearch:
    fields = dict(start_at=NOW - timedelta(days=1), end_at=NOW)
    fields.update(changes)
    return AuditSearch(**fields)


class Access:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[tuple] = []

    def can_read_project(self, tx, principal, project_id):
        self.calls.append(("project", tx, principal, project_id))
        return self.allowed

    def can_read_deployment(self, tx, principal):
        self.calls.append(("deployment", tx, principal))
        return self.allowed


class Repository:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def list_events(self, tx, *, project_id, search):
        self.calls.append(("list", tx, project_id, search))
        return AuditPage((), None, False)

    def get_event(self, tx, *, project_id, event_id):
        self.calls.append(("get", tx, project_id, event_id))
        return None


class AuditQueryTests(unittest.TestCase):
    def test_denied_before_repository_for_all_operations(self) -> None:
        access, repo, tx = Access(False), Repository(), object()
        service = AuditQueryService(access=access, repository=repo)
        event_id = uuid.uuid4()
        operations = (
            lambda: service.list_project(tx, "principal", PROJECT_ID, search()),
            lambda: service.get_project(tx, "principal", PROJECT_ID, event_id),
            lambda: service.list_deployment(tx, "principal", search()),
            lambda: service.get_deployment(tx, "principal", event_id),
        )
        for operation in operations:
            with self.assertRaises(AuditAccessDenied):
                operation()
        self.assertEqual(repo.calls, [])
        self.assertEqual(len(access.calls), 4)

    def test_allowed_calls_are_scope_fixed(self) -> None:
        access, repo, tx = Access(True), Repository(), object()
        service = AuditQueryService(access=access, repository=repo)
        query, event_id = search(), uuid.uuid4()
        service.list_project(tx, "principal", PROJECT_ID, query)
        service.get_project(tx, "principal", PROJECT_ID, event_id)
        service.list_deployment(tx, "principal", query)
        service.get_deployment(tx, "principal", event_id)
        self.assertEqual([call[2] for call in repo.calls], [PROJECT_ID, PROJECT_ID, None, None])

    def test_query_bounds_and_filters(self) -> None:
        for changes in (
            {"start_at": NOW}, {"start_at": NOW - timedelta(days=32)},
            {"page_size": 0}, {"page_size": 201}, {"page_size": True},
            {"action": "raw text"}, {"outcome": "UNKNOWN"},
            {"target_object_type": "../DOC-01"},
            {"trace_id": uuid.UUID(int=0)},
        ):
            with self.subTest(changes=changes), self.assertRaises(AuditQueryError):
                search(**changes)
        with self.assertRaises(AuditQueryError):
            AuditPosition(NOW.replace(tzinfo=None), uuid.uuid4())
        with self.assertRaises(AuditQueryError):
            AuditPosition("not-a-time", uuid.uuid4())
        with self.assertRaises(AuditQueryError):
            AuditSearch(start_at="not-a-time", end_at=NOW)

    def test_invalid_identifiers_fail_before_repository(self) -> None:
        repo = Repository()
        service = AuditQueryService(access=Access(True), repository=repo)
        with self.assertRaises(AuditQueryError):
            service.list_project(object(), "principal", uuid.UUID(int=0), search())
        with self.assertRaises(AuditQueryError):
            service.get_deployment(object(), "principal", uuid.UUID(int=0))
        with self.assertRaises(AuditQueryError):
            service.list_deployment(object(), "principal", object())
        self.assertEqual(repo.calls, [])

    def test_missing_dependencies_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            AuditQueryService(access=None, repository=Repository())
        with self.assertRaises(ValueError):
            AuditQueryService(access=Access(True), repository=None)


if __name__ == "__main__":
    unittest.main()
