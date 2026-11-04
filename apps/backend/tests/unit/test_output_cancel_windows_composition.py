from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi import APIRouter

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output import (
    ProductionOutputCancelStartupError,
    create_windows_output_cancel_router,
)
from plm_assistant.modules.output.infrastructure.cancel_access import (
    SqlAlchemyOutputRequestCancelAccess,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
)


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        self.requester = uuid.uuid4()
        self.project = uuid.uuid4()
        self.transaction = object()
        self.session_access = Mock()
        self.authorization = Mock()
        self.access = SqlAlchemyOutputRequestCancelAccess(
            authorization=self.authorization, session_access=self.session_access,
        )

    def test_authentication_delegates_same_transaction_and_tokens(self):
        now = datetime.now(timezone.utc)
        self.session_access.authenticated_user.return_value = self.actor
        self.assertEqual(self.access.authenticated_user(
            self.transaction, session_token=b"s" * 32,
            csrf_token=b"c" * 32, now=now,
        ), self.actor)
        self.session_access.authenticated_user.assert_called_once_with(
            self.transaction, session_token=b"s" * 32,
            csrf_token=b"c" * 32, now=now,
        )

    def test_creator_can_cancel_without_project_manager_policy(self):
        self.assertTrue(self.access.require_canceller(
            self.transaction, user_id=self.requester, project_id=self.project,
            requester_id=self.requester,
        ))
        self.authorization.require_in_transaction.assert_not_called()

    def test_noncreator_uses_project_manager_only_policy(self):
        self.assertTrue(self.access.require_canceller(
            self.transaction, user_id=self.actor, project_id=self.project,
            requester_id=self.requester,
        ))
        self.authorization.require_in_transaction.assert_called_once_with(
            self.transaction, user_id=self.actor, project_id=self.project,
            operation="OUTPUT_REQUEST_CANCEL",
        )

    def test_nonmanager_is_denied_without_leaking_project_facts(self):
        self.authorization.require_in_transaction.side_effect = (
            ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        )
        self.assertFalse(self.access.require_canceller(
            self.transaction, user_id=self.actor, project_id=self.project,
            requester_id=self.requester,
        ))


class WindowsCompositionTests(unittest.TestCase):
    def test_factory_builds_output_cancel_service_from_required_dependencies(self):
        runtime = Mock()
        sessions, origins, guard, audit = object(), object(), object(), object()
        expected = APIRouter()
        with patch(
            "plm_assistant.entrypoints.windows_output.create_output_request_cancel_router",
            return_value=expected,
        ) as create_router:
            result = create_windows_output_cancel_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit,
            )
        self.assertIs(result, expected)
        create_router.assert_called_once()
        self.assertIs(create_router.call_args.kwargs["sessions"], sessions)
        self.assertIs(create_router.call_args.kwargs["origins"], origins)
        service = create_router.call_args.kwargs["service"]
        self.assertIs(service._uow, runtime.unit_of_work)
        self.assertIs(service._guard, guard)
        self.assertIs(service._audit, audit)

    def test_missing_dependency_fails_closed(self):
        with self.assertRaises(ProductionOutputCancelStartupError):
            create_windows_output_cancel_router(
                runtime=None, sessions=object(), origins=object(),
                license_guard=object(), audit=object(),
            )


class OptionalAppRouterTests(unittest.TestCase):
    def test_default_app_does_not_mount_cancel_router_and_explicit_app_can(self):
        path = "/api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel"
        default = create_app()
        self.assertFalse(any(getattr(route, "path", "") == path for route in default.routes))
        router = APIRouter()
        router.add_api_route(path, lambda: None, methods=["POST"])
        explicit = create_app(output_request_cancel_router=router)
        self.assertTrue(any(
            getattr(route, "path", "") == path and "POST" in route.methods
            for route in explicit.routes
        ), f"explicit app did not include cancel route; paths={[getattr(route, 'path', None) for route in explicit.routes]!r}")
