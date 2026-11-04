from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi import APIRouter

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output_create import (
    ProductionOutputCreateStartupError,
    create_windows_output_request_create_router,
)
from plm_assistant.modules.output.infrastructure.create_access import (
    SqlAlchemyOutputRequestCreateAccess,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
)


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        self.project = uuid.uuid4()
        self.tx = object()
        self.session_access = Mock()
        self.authorization = Mock()
        self.access = SqlAlchemyOutputRequestCreateAccess(
            authorization=self.authorization, session_access=self.session_access,
        )

    def test_session_csrf_and_project_create_policy_share_transaction(self):
        self.session_access.authenticated_user.return_value = self.actor
        self.authorization.require_in_transaction.return_value = Mock(
            user_id=self.actor, project_id=self.project,
            operation="OUTPUT_REQUEST_CREATE",
        )
        now = datetime.now(timezone.utc)
        self.assertEqual(self.access.authorized_creator(
            self.tx, project_id=self.project, session_token=b"s" * 32,
            csrf_token=b"c" * 32, trace_id=uuid.uuid4(), now=now,
        ), self.actor)
        self.session_access.authenticated_user.assert_called_once_with(
            self.tx, session_token=b"s" * 32, csrf_token=b"c" * 32, now=now,
        )
        self.authorization.require_in_transaction.assert_called_once_with(
            self.tx, user_id=self.actor, project_id=self.project,
            operation="OUTPUT_REQUEST_CREATE",
        )

    def test_missing_session_or_membership_is_denied(self):
        self.session_access.authenticated_user.return_value = None
        self.assertIsNone(self.access.authorized_creator(
            self.tx, project_id=self.project, session_token=b"s" * 32,
            csrf_token=b"c" * 32, trace_id=uuid.uuid4(),
            now=datetime.now(timezone.utc),
        ))
        self.session_access.authenticated_user.return_value = self.actor
        self.authorization.require_in_transaction.side_effect = (
            ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        )
        self.assertIsNone(self.access.authorized_creator(
            self.tx, project_id=self.project, session_token=b"s" * 32,
            csrf_token=b"c" * 32, trace_id=uuid.uuid4(),
            now=datetime.now(timezone.utc),
        ))


class CompositionTests(unittest.TestCase):
    def test_factory_mounts_actual_create_adapter_with_fail_closed_packaged_trust(self):
        runtime = Mock()
        sessions, origins, guard, audit, session_access = (object(), object(), object(), object(), object())
        expected = APIRouter()
        with patch(
            "plm_assistant.entrypoints.windows_output_create.create_output_request_create_router",
            return_value=expected,
        ) as create_router:
            result = create_windows_output_request_create_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, session_access=session_access,
            )
        self.assertIs(result, expected)
        service = create_router.call_args.kwargs["service"]
        self.assertIs(service._uow, runtime.unit_of_work)
        self.assertIs(service._license, guard)
        self.assertIs(service._access._session_access, session_access)
        self.assertIs(service._audit, audit)
        self.assertIsNotNone(service._resolver)

    def test_missing_composition_dependency_fails_closed(self):
        with self.assertRaises(ProductionOutputCreateStartupError):
            create_windows_output_request_create_router(
                runtime=None, sessions=object(), origins=object(),
                license_guard=object(), audit=object(),
            )

    def test_create_route_is_opt_in(self):
        path = "/api/v1/projects/{project_id}/output-requests"
        self.assertNotIn(path, create_app().openapi().get("paths", {}))
        router = APIRouter()
        router.add_api_route(path, lambda: None, methods=["POST"])
        self.assertIn("post", create_app(
            output_request_create_router=router,
        ).openapi().get("paths", {}).get(path, {}))


if __name__ == "__main__":
    unittest.main()
