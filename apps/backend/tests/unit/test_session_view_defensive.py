"""Pre-SQL refusal and projection dispatch contracts, not successful SQL mocks."""

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.session_view import resolve_session_view
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView


class SessionViewDefensiveTests(unittest.TestCase):
    def test_required_dependencies_and_invalid_identity_do_not_open_uow(self):
        uow, projects = Mock(), Mock()
        for dependencies in ((None, projects), (uow, None)):
            with self.subTest(dependencies=dependencies), self.assertRaises(ValueError):
                SqlAlchemySessionView(unit_of_work=dependencies[0], projects=dependencies[1])
        view = SqlAlchemySessionView(unit_of_work=uow, projects=projects)
        for user_id in (None, True, str(uuid.uuid4()), uuid.UUID(int=0)):
            with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                view.resolve(user_id)
        uow.assert_not_called()
        projects.for_user.assert_not_called()

    def test_real_inactive_session_and_wrong_session_refuse_before_sql(self):
        projects = Mock()
        view = SqlAlchemySessionView(unit_of_work=Mock(), projects=projects)
        # A genuine unbound Session has no active transaction; no execute override.
        with Session() as session:
            self.assertFalse(session.in_transaction())
            for source in (None, object(), session):
                with self.subTest(source=type(source).__name__), self.assertRaisesRegex(
                    RuntimeError, 'Active identity transaction required'
                ):
                    view._resolve(SimpleNamespace(session=source), uuid.uuid4())
            self.assertFalse(session.in_transaction())
        projects.for_user.assert_not_called()

    def test_token_bound_projection_has_priority_and_never_falls_back(self):
        user_id, token, result = uuid.uuid4(), bytes(range(32)), object()
        bound, legacy = Mock(return_value=result), Mock()
        views = SimpleNamespace(resolve_for_session=bound, resolve=legacy)
        self.assertIs(resolve_session_view(views, user_id, token), result)
        bound.assert_called_once_with(user_id=user_id, session_token=token)
        legacy.assert_not_called()
        for failure in (LookupError('Unavailable'), RuntimeError('Source failure')):
            bound.reset_mock()
            bound.side_effect = failure
            with self.subTest(failure=type(failure).__name__), self.assertRaises(type(failure)):
                resolve_session_view(views, user_id, token)
            bound.assert_called_once_with(user_id=user_id, session_token=token)
            legacy.assert_not_called()

    def test_invalid_bound_projection_refuses_and_absent_bound_preserves_legacy(self):
        user_id, token, result = uuid.uuid4(), bytes(range(32)), object()
        for invalid in (False, 1, 'not-callable', object()):
            legacy = Mock()
            with self.subTest(invalid=type(invalid).__name__), self.assertRaisesRegex(
                ValueError, 'Session projection unavailable'
            ):
                resolve_session_view(SimpleNamespace(resolve_for_session=invalid,
                                                     resolve=legacy), user_id, token)
            legacy.assert_not_called()
        for has_attribute in (False, True):
            legacy = Mock(return_value=result)
            views = SimpleNamespace(resolve=legacy)
            if has_attribute:
                views.resolve_for_session = None
            with self.subTest(has_attribute=has_attribute):
                self.assertIs(resolve_session_view(views, user_id, token), result)
                legacy.assert_called_once_with(user_id)
