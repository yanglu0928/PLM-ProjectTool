from __future__ import annotations

import unittest
from typing import Any, cast

from sqlalchemy.orm import Session

from plm_assistant.modules.platform.infrastructure.database import (
    SqlAlchemyUnitOfWork,
    UnitOfWorkStateError,
)


class FakeTransaction:
    def __init__(self) -> None:
        self.is_active = True
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1
        self.is_active = False

    def rollback(self) -> None:
        self.rollback_count += 1
        self.is_active = False


class FakeSession:
    def __init__(self) -> None:
        self.transaction = FakeTransaction()
        self.begin_count = 0
        self.close_count = 0

    def begin(self) -> FakeTransaction:
        self.begin_count += 1
        return self.transaction

    def close(self) -> None:
        self.close_count += 1


class FailingBeginSession(FakeSession):
    def begin(self) -> FakeTransaction:
        self.begin_count += 1
        raise RuntimeError("begin failed")


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> Session:
        session = FakeSession()
        self.sessions.append(session)
        return cast(Session, cast(Any, session))


class SqlAlchemyUnitOfWorkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = SessionFactory()
        self.unit_of_work = SqlAlchemyUnitOfWork(self.factory)

    def test_explicit_commit_commits_once_and_closes(self) -> None:
        with self.unit_of_work as active:
            session = cast(Any, active.session)
            active.commit()

        self.assertEqual(session.transaction.commit_count, 1)
        self.assertEqual(session.transaction.rollback_count, 0)
        self.assertEqual(session.close_count, 1)

    def test_scope_without_commit_rolls_back_and_closes(self) -> None:
        with self.unit_of_work as active:
            session = cast(Any, active.session)

        self.assertEqual(session.transaction.commit_count, 0)
        self.assertEqual(session.transaction.rollback_count, 1)
        self.assertEqual(session.close_count, 1)

    def test_exception_rolls_back_and_preserves_original_error(self) -> None:
        session: Any = None
        with self.assertRaisesRegex(RuntimeError, "application failure"):
            with self.unit_of_work as active:
                session = cast(Any, active.session)
                raise RuntimeError("application failure")

        self.assertEqual(session.transaction.rollback_count, 1)
        self.assertEqual(session.close_count, 1)

    def test_explicit_rollback_cannot_be_followed_by_commit(self) -> None:
        with self.unit_of_work as active:
            active.rollback()
            with self.assertRaises(UnitOfWorkStateError):
                active.commit()

    def test_unit_of_work_is_single_use(self) -> None:
        with self.unit_of_work:
            pass
        with self.assertRaises(UnitOfWorkStateError):
            self.unit_of_work.__enter__()

    def test_new_unit_of_work_uses_a_new_session(self) -> None:
        first = SqlAlchemyUnitOfWork(self.factory)
        second = SqlAlchemyUnitOfWork(self.factory)
        with first as active_first:
            first_session = active_first.session
        with second as active_second:
            second_session = active_second.session
        self.assertIsNot(first_session, second_session)

    def test_begin_failure_still_closes_session(self) -> None:
        session = FailingBeginSession()
        unit_of_work = SqlAlchemyUnitOfWork(
            lambda: cast(Session, cast(Any, session))
        )
        with self.assertRaisesRegex(RuntimeError, "begin failed"):
            unit_of_work.__enter__()
        self.assertEqual(session.close_count, 1)


if __name__ == "__main__":
    unittest.main()
