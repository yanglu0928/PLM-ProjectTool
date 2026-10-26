from __future__ import annotations

import tempfile
import unittest
import uuid
import inspect
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import APIRouter
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError,
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
    create_production_platform_trace_app,
    create_production_platform_write_trace_app,
)
from plm_assistant.entrypoints.serve_windows import main as serve_windows_main
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import GlobalReferenceCandidateCursorCodec
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec
from plm_assistant.modules.trace.application.page_graph import TraceGraphCursorCodec
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec
from plm_assistant.modules.solution.application.outline_review_subject import OutlineReviewSubjectOwner
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.api.structured_spec_list_cursor import (
    StructuredSpecListCursorCodec,
)
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.review.api.list_cursor import ReviewListCursorCodec
from plm_assistant.entrypoints.windows_ai_read_cursor import WindowsAIReadCursorCodecs
from plm_assistant.entrypoints.windows_capability import WindowsCapabilityRouters
from plm_assistant.entrypoints.windows_handover import WindowsHandoverRouters
from plm_assistant.entrypoints.windows_survey import WindowsSurveyRouters
from plm_assistant.entrypoints.windows_requirement import WindowsRequirementRouters
from plm_assistant.entrypoints.windows_prototype import WindowsPrototypeRouters
from plm_assistant.entrypoints.windows_handover_action import (
    WindowsHandoverActionWriteRouters,
)


class _ContractMaintenanceAdmission:
    """Route-only tests have no PG; real gate is proven by PG validation."""

    @contextmanager
    def admit(self):
        yield object()


class ProductionLoginTests(unittest.TestCase):
    def test_missing_plan_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_plan_list_cursor_codec",
                    side_effect=RuntimeError("private Plan cursor key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_review_list_cursor_key_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import (
            SecretListCursorCodec,
        )

        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with ExitStack() as stack:
                    prefix = "plm_assistant.entrypoints.production_login."
                    for name, value in (
                        ("read_database_url", "postgresql+psycopg://localhost/test"),
                        ("create_database_runtime", runtime),
                        ("_schema_current", True),
                        ("create_windows_secret_list_cursor_codec",
                         SecretListCursorCodec(b"q" * 32)),
                        ("create_windows_project_member_cursor_codec",
                         MemberListCursorCodec(b"m" * 32)),
                        ("create_windows_project_department_cursor_codec",
                         DepartmentListCursorCodec(b"d" * 32)),
                    ):
                        stack.enter_context(patch(prefix + name, return_value=value))
                    stack.enter_context(patch(
                        "plm_assistant.entrypoints.windows_license_runtime."
                        "create_windows_license_services",
                        return_value=Mock(guard=Mock()),
                    ))
                    failed = stack.enter_context(patch(
                        prefix + "create_windows_review_list_cursor_codec",
                        side_effect=RuntimeError("private Review cursor key missing"),
                    ))
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_structured_spec_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_structured_spec_list_cursor_codec",
                    side_effect=RuntimeError("private spec cursor key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_section_version_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_section_version_list_cursor_codec",
                    side_effect=RuntimeError("private cursor key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_global_candidate_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch("plm_assistant.entrypoints.production_login.read_database_url",
                           return_value="postgresql+psycopg://localhost/test"), patch(
                           "plm_assistant.entrypoints.production_login.create_database_runtime",
                           return_value=runtime), patch(
                           "plm_assistant.entrypoints.production_login._schema_current",
                           return_value=True), patch(
                           "plm_assistant.entrypoints.windows_license_runtime."
                           "create_windows_license_services",
                           return_value=Mock(guard=Mock())), patch(
                           "plm_assistant.entrypoints.production_login."
                           "create_windows_project_global_reference_candidate_cursor_codec",
                           side_effect=RuntimeError("private missing candidate cursor key")) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                self.assertNotIn("private", str(caught.exception))
                failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def test_missing_outline_version_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_outline_version_list_cursor_codec",
                    side_effect=RuntimeError("private history key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_section_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_section_list_cursor_codec",
                    side_effect=RuntimeError("private Section cursor key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_outline_cursor_key_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_outline_list_cursor_codec",
                    side_effect=RuntimeError("private Outline cursor key missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_outline_read_composition_failure_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_outline_read_router",
                    side_effect=RuntimeError("private outline trust missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_outline_review_owner_failure_disposes_both_platform_modes(self):
        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with self.subTest(factory=factory.__name__):
                runtime = Mock()
                runtime.is_ready.return_value = True
                with patch(
                    "plm_assistant.entrypoints.production_login.read_database_url",
                    return_value="postgresql+psycopg://localhost/test",
                ), patch(
                    "plm_assistant.entrypoints.production_login.create_database_runtime",
                    return_value=runtime,
                ), patch(
                    "plm_assistant.entrypoints.production_login._schema_current",
                    return_value=True,
                ), patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_secret_list_cursor_codec",
                    return_value=Mock(),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_project_member_cursor_codec",
                    return_value=MemberListCursorCodec(b"m" * 32),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_project_department_cursor_codec",
                    return_value=DepartmentListCursorCodec(b"d" * 32),
                ), patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_outline_review_subject",
                    side_effect=RuntimeError("private Outline review source missing"),
                ) as failed:
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
                runtime.dispose.assert_called_once()

    def test_missing_global_reference_list_cursor_key_disposes_platform_runtime(self):
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login."
                   "create_windows_global_reference_list_cursor_codec",
                   side_effect=RuntimeError("private missing GLOBAL Reference cursor key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(self.settings(("http://localhost",)))
        self.assertNotIn("private", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_missing_reference_list_cursor_key_disposes_platform_runtime(self):
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login."
                   "create_windows_project_reference_list_cursor_codec",
                   side_effect=RuntimeError("private missing Reference cursor key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(self.settings(("http://localhost",)))
        self.assertNotIn("private", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_user_write_constructors_fail_closed_dispose_write_only(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for dependency in ('SqlAlchemyUserCreateResultRepository','UserCreateReplayVerifier',
                           'ManagedUserCreateService','create_user_create_router',
                           'SqlAlchemyUserNamePatchRepository','UserNamePatchService','create_user_name_patch_router'):
            runtime=Mock();runtime.is_ready.return_value=True
            with ExitStack() as stack:
                for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                    ('create_database_runtime',runtime),('_schema_current',True),
                    ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                    ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                    ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                    stack.enter_context(patch(prefix+name,return_value=value))
                stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private User creation failure')))
                with self.assertRaises(ProductionLoginStartupError) as caught:create_production_platform_write_app(self.settings(('http://localhost',)))
                failed.assert_called_once();self.assertNotIn('private',str(caught.exception))
            runtime.dispose.assert_called_once()

    def test_user_list_dependencies_fail_closed_dispose_both_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for factory in (create_production_platform_app,create_production_platform_write_app):
            for dependency in ('AuthorizedUserListService','create_user_list_router','create_windows_user_list_cursor_codec'):
                runtime=Mock();runtime.is_ready.return_value=True
                with ExitStack() as stack:
                    for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                        ('create_database_runtime',runtime),('_schema_current',True),
                        ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                        ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                        ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                        stack.enter_context(patch(prefix+name,return_value=value))
                    stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                    failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private user list failure')))
                    with self.assertRaises(ProductionLoginStartupError) as caught:factory(self.settings(('http://localhost',)))
                    self.assertNotIn('private',str(caught.exception));failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def test_user_detail_dependencies_fail_closed_and_dispose_both_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for factory in (create_production_platform_app,create_production_platform_write_app):
            for dependency in ('AuthorizedUserReadService','SqlAlchemyUserReadRepository','create_user_detail_router'):
                runtime=Mock();runtime.is_ready.return_value=True
                with ExitStack() as stack:
                    for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                        ('create_database_runtime',runtime),('_schema_current',True),
                        ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                        ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                        ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                        stack.enter_context(patch(prefix+name,return_value=value))
                    stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                    failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private user detail constructor')))
                    with self.assertRaises(ProductionLoginStartupError) as caught:factory(self.settings(('http://localhost',)))
                    self.assertNotIn('private',str(caught.exception));failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def test_retry_source_constructor_failure_disposes_write_runtime(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for dependency in ('AuditUserRetrySourceReader','AuditUserRetryJobSources',
            'SqlAlchemyAuditUserRetryJobSources','SqlAlchemyAuditUserRetryFailureSources'):
            runtime=Mock();runtime.is_ready.return_value=True
            with ExitStack() as stack:
                for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                    ('create_database_runtime',runtime),('_schema_current',True),
                    ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                    ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                    ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                    stack.enter_context(patch(prefix+name,return_value=value))
                stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private constructor')))
                with self.assertRaises(ProductionLoginStartupError) as caught:
                    create_production_platform_write_app(self.settings(('http://localhost',)))
                self.assertNotIn('private',str(caught.exception));failed.assert_called_once()
            runtime.dispose.assert_called_once()

    def test_export_composition_constructor_failure_disposes_both_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for factory in (create_production_platform_app,create_production_platform_write_app):
            for dependency in ('AuditExportContentReader','create_audit_export_result_router','create_audit_export_download_router'):
                runtime=Mock();runtime.is_ready.return_value=True
                with ExitStack() as stack:
                    for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                        ('create_database_runtime',runtime),('_schema_current',True),
                        ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                        ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                        ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                        stack.enter_context(patch(prefix+name,return_value=value))
                    stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                    failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private failure')))
                    with self.assertRaises(ProductionLoginStartupError) as caught:factory(self.settings(('http://localhost',)))
                    self.assertNotIn('private',str(caught.exception));failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def setUp(self) -> None:
        self.maintenance_engine = Mock()
        self.enterContext(patch(
            'plm_assistant.entrypoints.production_login.create_engine',
            return_value=self.maintenance_engine))
        self.enterContext(patch(
            'plm_assistant.entrypoints.production_login.PostgresMaintenanceAdmission',
            return_value=_ContractMaintenanceAdmission()))
        from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
        self.enterContext(patch('plm_assistant.entrypoints.production_login.create_windows_user_list_cursor_codec',
            return_value=UserListCursorCodec(b'u'*32)))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_job_list_cursor_codec",
            return_value=JobListCursorCodec(b"j" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_audit_cursor_codec",
            return_value=AuditListCursorCodec(b"a"*32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_provider_list_cursor_codec",
            return_value=ProviderListCursorCodec(b"i" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_model_list_cursor_codec",
            return_value=ModelListCursorCodec(b"n" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_prompt_list_cursor_codec",
            return_value=PromptListCursorCodec(b"p" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_read_cursor_codecs",
            return_value=WindowsAIReadCursorCodecs(
                AITaskListCursorCodec(b"r" * 32),
                AIInvocationListCursorCodec(b"r" * 32),
            ),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_capability_routers",
            side_effect=lambda *args, include_write, **kwargs: WindowsCapabilityRouters(
                APIRouter(), APIRouter() if include_write else None,
                APIRouter() if include_write else None,
                APIRouter() if include_write else None,
                APIRouter() if include_write else None,
            ),
        ))
        self.handover_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_handover_routers",
            side_effect=lambda *args, include_write, **kwargs: WindowsHandoverRouters(
                APIRouter(), APIRouter() if include_write else None,
                APIRouter() if include_write else None,
            ),
        ))
        self.survey_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_survey_routers",
            side_effect=lambda *args, include_write, **kwargs: WindowsSurveyRouters(
                APIRouter(), APIRouter() if include_write else None,
                APIRouter() if include_write else None,
            ),
        ))
        self.requirement_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_requirement_routers",
            side_effect=lambda *args, include_write, **kwargs: (
                WindowsRequirementRouters(
                    APIRouter(), APIRouter(), APIRouter(), APIRouter(),
                    APIRouter() if include_write else None,
                )
            ),
        ))
        self.prototype_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_prototype_routers",
            side_effect=lambda *args, include_write, **kwargs: (
                WindowsPrototypeRouters(
                    APIRouter(), APIRouter(), APIRouter(), APIRouter(),
                    APIRouter(), APIRouter() if include_write else None,
                )
            ),
        ))
        self.handover_action_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_handover_action_read_router",
            return_value=APIRouter(),
        ))
        self.handover_action_write_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_handover_action_write_routers",
            return_value=WindowsHandoverActionWriteRouters(APIRouter(), APIRouter()),
        ))
        self.project_review_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_project_review_router",
            return_value=APIRouter(),
        ))
        self.project_review_read_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_review_read_router",
            return_value=APIRouter(),
        ))
        self.project_review_list_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_review_list_router",
            return_value=APIRouter(),
        ))
        self.workflow_checklist_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_workflow_checklist_record_router",
            return_value=APIRouter(),
        ))
        self.workflow_checklist_qualification_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_workflow_checklist_qualification_router",
            return_value=APIRouter(),
        ))
        self.workflow_transition_factory = self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_workflow_stage_transition_router",
            return_value=APIRouter(),
        ))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",
            return_value=DocumentListCursorCodec(b"x" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_reference_list_cursor_codec",
            return_value=ReferenceListCursorCodec(b"r" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_global_reference_list_cursor_codec",
            return_value=GlobalReferenceListCursorCodec(b"g" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_global_reference_candidate_cursor_codec",
            return_value=GlobalReferenceCandidateCursorCodec(b"c" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_outline_list_cursor_codec",
            return_value=OutlineListCursorCodec(b"o" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_plan_list_cursor_codec",
            return_value=PlanListCursorCodec(b"p" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_plan_version_list_cursor_codec",
            return_value=PlanVersionListCursorCodec(b"p" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_outline_version_list_cursor_codec",
            return_value=OutlineVersionListCursorCodec(b"v" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_section_version_list_cursor_codec",
            return_value=SectionVersionListCursorCodec(b"w" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_section_list_cursor_codec",
            return_value=SectionListCursorCodec(b"s" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_structured_spec_list_cursor_codec",
            return_value=StructuredSpecListCursorCodec(b"t" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_review_list_cursor_codec",
            return_value=ReviewListCursorCodec(b"r" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",
            return_value=VersionListCursorCodec(b"z" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",
            return_value=ParseListCursorCodec(b"p" * 32),
        ))

    def settings(self, origins: tuple[str, ...], *, egress: bool = False,
                 retrieval: bool = False) -> BootstrapSettings:
        policies = ({
            "reference": "minimal-document-text.v1",
            "operation_types": ["AI_TASK"], "data_categories": ["DOCUMENT_TEXT"],
            "ttl_minutes": 30, "max_record_count": 50,
            "max_payload_bytes": 1_048_576, "max_input_tokens": 32_768,
            "max_retry_attempts": 2, "risk_codes": ["EXTERNAL_PROCESSING"],
            "approval_roles": ["PROJECT_MANAGER"], "data_regions": ["cn-beijing"],
        },) if egress else ()
        return BootstrapSettings(
            data_root=Path(self.temp_dir.name), trusted_origins=origins,
            ai_egress_policies=policies,
            rag_retrieval_policies=({
                "reference": "fts.project.v1", "scope": "PROJECT",
                "rerank_policy_ref": "none.v1",
                "context_policy_ref": "project-documents.v1",
            },) if retrieval else (),
        )

    def test_missing_audit_cursor_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        for factory in (create_production_platform_app,create_production_platform_write_app):
            runtime=Mock();runtime.is_ready.return_value=True
            with ExitStack() as stack:
                prefix="plm_assistant.entrypoints.production_login."
                for name,value in (("read_database_url","postgresql+psycopg://test:synthetic@localhost/test"),
                    ("create_database_runtime",runtime),("_schema_current",True),
                    ("create_windows_secret_list_cursor_codec",SecretListCursorCodec(b"q"*32)),
                    ("create_windows_project_member_cursor_codec",MemberListCursorCodec(b"m"*32)),
                    ("create_windows_project_department_cursor_codec",DepartmentListCursorCodec(b"d"*32))):
                    stack.enter_context(patch(prefix+name,return_value=value))
                stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",return_value=Mock(guard=Mock())))
                stack.enter_context(patch(prefix+"create_windows_audit_cursor_codec",side_effect=RuntimeError("sensitive synthetic missing key")))
                with self.assertRaises(ProductionLoginStartupError) as exc:factory(self.settings(("http://localhost",)))
                self.assertNotIn("sensitive",str(exc.exception))
            runtime.dispose.assert_called_once()

    def test_missing_ai_provider_cursor_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        for factory in (create_production_platform_app, create_production_platform_write_app):
            runtime = Mock(); runtime.is_ready.return_value = True
            with ExitStack() as stack:
                prefix = "plm_assistant.entrypoints.production_login."
                for name, value in (("read_database_url", "postgresql+psycopg://localhost/test"),
                                    ("create_database_runtime", runtime), ("_schema_current", True),
                                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32))):
                    stack.enter_context(patch(prefix + name, return_value=value))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ))
                missing = stack.enter_context(patch(
                    prefix + "create_windows_ai_provider_list_cursor_codec",
                    side_effect=RuntimeError("private synthetic missing key"),
                ))
                with self.assertRaises(ProductionLoginStartupError) as caught:
                    factory(self.settings(("http://localhost",)))
                missing.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
            runtime.dispose.assert_called_once()

    def test_missing_ai_model_cursor_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        for factory in (create_production_platform_app, create_production_platform_write_app):
            runtime = Mock(); runtime.is_ready.return_value = True
            with ExitStack() as stack:
                prefix = "plm_assistant.entrypoints.production_login."
                for name, value in (("read_database_url", "postgresql+psycopg://localhost/test"),
                                    ("create_database_runtime", runtime), ("_schema_current", True),
                                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32))):
                    stack.enter_context(patch(prefix + name, return_value=value))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ))
                missing = stack.enter_context(patch(
                    prefix + "create_windows_ai_model_list_cursor_codec",
                    side_effect=RuntimeError("private synthetic missing key"),
                ))
                with self.assertRaises(ProductionLoginStartupError) as caught:
                    factory(self.settings(("http://localhost",)))
                missing.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
            runtime.dispose.assert_called_once()

    def test_missing_ai_prompt_cursor_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        for factory in (create_production_platform_app, create_production_platform_write_app):
            runtime = Mock(); runtime.is_ready.return_value = True
            with ExitStack() as stack:
                prefix = "plm_assistant.entrypoints.production_login."
                for name, value in (("read_database_url", "postgresql+psycopg://localhost/test"),
                                    ("create_database_runtime", runtime), ("_schema_current", True),
                                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32))):
                    stack.enter_context(patch(prefix + name, return_value=value))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=Mock(guard=Mock()),
                ))
                missing = stack.enter_context(patch(
                    prefix + "create_windows_ai_prompt_list_cursor_codec",
                    side_effect=RuntimeError("private synthetic missing key"),
                ))
                with self.assertRaises(ProductionLoginStartupError) as caught:
                    factory(self.settings(("http://localhost",)))
                missing.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
            runtime.dispose.assert_called_once()

    def test_ai_provider_create_dependency_fails_closed_only_in_write_mode(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        runtime = Mock(); runtime.is_ready.return_value = True
        prefix = "plm_assistant.entrypoints.production_login."
        with ExitStack() as stack:
            for name, value in (
                ("read_database_url", "postgresql+psycopg://localhost/test"),
                ("create_database_runtime", runtime), ("_schema_current", True),
                ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
            ):
                stack.enter_context(patch(prefix + name, return_value=value))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=Mock(guard=Mock()),
            ))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                return_value=Mock(),
            ))
            failed = stack.enter_context(patch(
                prefix + "AIProviderCreateService",
                side_effect=RuntimeError("private synthetic create dependency"),
            ))
            read_app = create_production_platform_app(self.settings(("http://localhost",)))
            with TestClient(read_app, base_url="http://localhost") as client:
                self.assertEqual(client.post("/api/v1/admin/ai/providers").status_code, 405)
            self.assertEqual(failed.call_count, 0)
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_write_app(self.settings(("http://localhost",)))
            failed.assert_called_once()
            self.assertNotIn("private", str(caught.exception))
        self.assertEqual(runtime.dispose.call_count, 2)

    def test_reference_write_constructor_failure_disposes_write_only(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec

        prefix = "plm_assistant.entrypoints.production_login."
        for name in ("create_windows_global_reference_revise_router",
                     "create_windows_project_reference_revise_router",
                     "create_windows_global_reference_eligibility_router",
                     "create_windows_global_reference_publication_router",
                     "create_windows_project_reference_eligibility_router"):
            runtime = Mock()
            runtime.is_ready.return_value = True
            with self.subTest(name=name), ExitStack() as stack:
                for dependency, value in (
                    ("read_database_url", "postgresql+psycopg://localhost/test"),
                    ("create_database_runtime", runtime),
                    ("_schema_current", True),
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                    ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                    ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                ):
                    stack.enter_context(patch(prefix + dependency, return_value=value))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=Mock(guard=Mock())))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                    return_value=Mock()))
                failed = stack.enter_context(patch(
                    prefix + name, side_effect=RuntimeError("private Reference write dependency")))
                read_app = create_production_platform_app(self.settings(("http://localhost",)))
                with TestClient(read_app, base_url="http://localhost") as client:
                    self.assertEqual(client.get("/health/ready").status_code, 200)
                self.assertEqual(failed.call_count, 0)
                with self.assertRaises(ProductionLoginStartupError) as caught:
                    create_production_platform_write_app(self.settings(("http://localhost",)))
                failed.assert_called_once()
                self.assertNotIn("private", str(caught.exception))
            self.assertEqual(runtime.dispose.call_count, 2)

    def test_ai_provider_patch_dependency_fails_closed_only_in_write_mode(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        runtime = Mock(); runtime.is_ready.return_value = True
        prefix = "plm_assistant.entrypoints.production_login."
        with ExitStack() as stack:
            for name, value in (
                ("read_database_url", "postgresql+psycopg://localhost/test"),
                ("create_database_runtime", runtime), ("_schema_current", True),
                ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
            ):
                stack.enter_context(patch(prefix + name, return_value=value))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=Mock(guard=Mock()),
            ))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                return_value=Mock(),
            ))
            failed = stack.enter_context(patch(
                prefix + "AIProviderAppendService",
                side_effect=RuntimeError("private synthetic patch dependency"),
            ))
            read_app = create_production_platform_app(self.settings(("http://localhost",)))
            with TestClient(read_app, base_url="http://localhost") as client:
                self.assertEqual(client.patch("/api/v1/admin/ai/providers/" + str(uuid.uuid4())).status_code, 405)
            self.assertEqual(failed.call_count, 0)
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_write_app(self.settings(("http://localhost",)))
            failed.assert_called_once()
            self.assertNotIn("private", str(caught.exception))
        self.assertEqual(runtime.dispose.call_count, 2)

    def test_job_list_dependencies_fail_closed_and_dispose_both_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix = "plm_assistant.entrypoints.production_login."
        for factory in (create_production_platform_app, create_production_platform_write_app):
            for dependency in ("create_windows_job_list_cursor_codec", "AuthorizedJobListService", "create_job_list_router"):
                runtime = Mock(); runtime.is_ready.return_value = True
                with ExitStack() as stack:
                    for name, value in (
                        ("read_database_url", "postgresql+psycopg://localhost/test"),
                        ("create_database_runtime", runtime), ("_schema_current", True),
                        ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q"*32)),
                        ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m"*32)),
                        ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d"*32)),
                    ): stack.enter_context(patch(prefix+name, return_value=value))
                    stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services", return_value=Mock(guard=Mock())))
                    failed = stack.enter_context(patch(prefix+dependency, side_effect=RuntimeError("private dependency detail")))
                    with self.assertRaises(ProductionLoginStartupError) as caught:
                        factory(self.settings(("http://localhost",)))
                    self.assertNotIn("private", str(caught.exception))
                    failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def test_empty_or_insecure_origin_never_reads_credential(self) -> None:
        with patch("plm_assistant.entrypoints.production_login.read_database_url") as reader:
            for origins in ((), ("http://plm.example.test",)):
                with self.subTest(origins=origins):
                    with self.assertRaises(ProductionLoginStartupError):
                        create_production_login_app(self.settings(origins))
            reader.assert_not_called()

    def test_missing_credential_fails_without_revealing_target(self) -> None:
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   side_effect=RuntimeError("synthetic-password")):
            with self.assertRaises(ProductionLoginStartupError) as captured:
                create_production_login_app(self.settings(("http://localhost",)))
        self.assertNotIn("synthetic-password", str(captured.exception))

    def test_database_unavailable_disposes_and_does_not_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = False
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_login_app(self.settings(("http://localhost",)))
        runtime.dispose.assert_called_once()

    def test_outdated_schema_disposes_and_does_not_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=False):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_login_app(self.settings(("http://localhost",)))
        runtime.dispose.assert_called_once()

    def test_opt_in_route_and_shutdown_disposal(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True):
            app = create_production_login_app(self.settings(("http://localhost",)))
        with TestClient(create_app(), base_url="http://localhost") as bare:
            self.assertEqual(bare.post("/api/v1/auth/login").status_code, 404)
            self.assertEqual(bare.get("/api/v1/projects").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects").status_code, 404)
            self.assertEqual(bare.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003:validate").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(bare.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 404)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 404)
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.get("/health/ready").status_code, 200)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003:validate").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "global-reference-candidates").status_code, 404)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 404)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 404)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 404)
            response = client.post("/api/v1/auth/login", headers={"origin": "http://evil.test"},
                                   json={"username": "a", "password": "b"})
            self.assertEqual(response.status_code, 403)
        runtime.dispose.assert_called_once()
        self.maintenance_engine.dispose.assert_called_once()

    def test_windows_launcher_passes_nonsecret_settings_to_factory(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv", ["serve_windows", str(bootstrap)]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_login_app",
             return_value="synthetic-app") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.kwargs["factory"], True)
            self.assertEqual(run.call_args.kwargs["proxy_headers"], False)
            self.assertEqual(run.call_args.args[0](), "synthetic-app")
            factory.assert_called_once_with(settings)

    def test_windows_launcher_rejects_nonloopback_plain_http(self) -> None:
        settings = BootstrapSettings(
            data_root=Path(self.temp_dir.name), bind_host="0.0.0.0",
            trusted_origins=("https://plm.example.test",),
        )
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv", ["serve_windows", str(bootstrap)]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run:
            self.assertEqual(serve_windows_main(), 1)
            run.assert_not_called()

    def test_platform_requires_license_and_cursor_key_before_routes_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())) as license_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   side_effect=RuntimeError("synthetic missing cursor key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing cursor key", str(caught.exception))
        license_factory.assert_called_once_with(runtime, settings)
        runtime.dispose.assert_called_once()

    def test_platform_mounts_read_only_with_explicit_trust_sources(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",), egress=True)
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                    "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                    return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                    "plm_assistant.entrypoints.production_login.create_windows_ai_egress_router") as egress_factory:
            app = create_production_platform_app(settings)
        egress_factory.assert_not_called()
        self.handover_action_factory.assert_called_once()
        self.survey_factory.assert_called_once()
        self.requirement_factory.assert_called_once()
        self.assertFalse(
            self.requirement_factory.call_args.kwargs["include_write"]
        )
        self.prototype_factory.assert_called_once()
        self.assertFalse(
            self.prototype_factory.call_args.kwargs["include_write"]
        )
        self.handover_action_write_factory.assert_not_called()
        self.project_review_factory.assert_not_called()
        self.project_review_read_factory.assert_called_once()
        self.project_review_list_factory.assert_called_once()
        outline_owner = self.project_review_read_factory.call_args.kwargs["outline_subject"]
        self.assertIs(type(outline_owner), OutlineReviewSubjectOwner)
        self.assertIs(self.project_review_list_factory.call_args.kwargs["outline_subject"],
                      outline_owner)
        self.workflow_checklist_factory.assert_not_called()
        self.workflow_checklist_qualification_factory.assert_not_called()
        self.workflow_transition_factory.assert_not_called()
        self.assertFalse(any(
            getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/solution-sections/{section_id}/"
            "versions/{section_version_id}:submit-review"
            and "POST" in getattr(route, "methods", ())
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", ())
        ))
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003:validate").status_code, 405)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans"
            ).status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002").status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans"
            ).status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions").status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions/00000000-0000-0000-0000-000000000002:revise"
            ).status_code, 405)
            self.assertEqual(client.post(
                "/api/v1/global/reference-solutions/"
                "00000000-0000-0000-0000-000000000002:revise"
            ).status_code, 405)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines/00000000-0000-0000-0000-000000000002").status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections").status_code, 404)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections/00000000-0000-0000-0000-000000000002/versions"
            ).status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections/00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions/00000000-0000-0000-0000-000000000002").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "global-reference-candidates").status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/global/reference-solutions").status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations:preview"
            ).status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations"
            ).status_code, 404)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations:lookup-operation"
            ).status_code, 404)
            self.assertEqual(client.get("/api/v1/admin/secrets").status_code, 401)
            self.assertEqual(client.get("/api/v1/admin/ai/models").status_code, 401)
            self.assertEqual(client.post("/api/v1/admin/ai/models").status_code, 405)
            self.assertEqual(client.post("/api/v1/admin/ai/models/00000000-0000-0000-0000-000000000001:set-state").status_code, 405)
            self.assertEqual(client.get("/api/v1/admin/audit-events").status_code,401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/audit-events").status_code,401)
            self.assertEqual(client.get("/api/v1/admin/secrets/" + "1" * 36).status_code, 422)
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 405)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 403)
            self.assertEqual(client.post("/api/v1/global/document-uploads").status_code, 404)
            self.assertEqual(client.put("/api/v1/global/document-uploads/00000000-0000-0000-0000-000000000001/content").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 403)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 403)
            self.assertEqual(client.get("/health/ready").status_code, 200)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/egress-previews"
            ).status_code, 404)
        runtime.dispose.assert_called_once()

    def test_platform_download_storage_failure_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.LocalFileStorage",
                   side_effect=RuntimeError("synthetic-storage-path")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic-storage-path", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_member_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   side_effect=RuntimeError("synthetic missing member key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing member key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_department_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   side_effect=RuntimeError("synthetic missing department key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing department key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_document_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Document key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Document key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_version_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Version key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Version key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_windows_launcher_platform_mode_is_explicit(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv",
             ["serve_windows", str(bootstrap), "--platform"]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_platform_app",
             return_value="synthetic-platform") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.args[0](), "synthetic-platform")
            self.assertEqual(run.call_args.kwargs["workers"], 1)
            factory.assert_called_once_with(settings)

    def test_missing_parse_cursor_key_disposes_platform(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Parse key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Parse key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_write_mode_missing_master_key_disposes_without_publishing(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_platform_write_app(settings)
        runtime.dispose.assert_called_once()

    def test_write_mode_mounts_only_after_all_sources_exist(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(
            ("http://localhost",), egress=True, retrieval=True,
        )
        egress_router = APIRouter()
        retrieval_router, retrieval_cancel_router = APIRouter(), APIRouter()
        validation_router = APIRouter()
        plan_version_create_router = APIRouter()
        plan_version_create_router.add_api_route(
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions",
            lambda: None, methods=["POST"])
        plan_submit_router = APIRouter()
        plan_submit_router.add_api_route(
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
            "{plan_version_id}:submit-review", lambda: None, methods=["POST"])
        validation_service = Mock()
        retrieval_cancel_owner = Mock(cancel=Mock())

        @egress_router.post("/api/v1/projects/{project_id}/egress-previews", status_code=204)
        def synthetic_egress_mount(project_id: str) -> None:
            del project_id
        @retrieval_router.get(
            "/api/v1/projects/{project_id}/retrieval-runs/{run_id}",
            status_code=204,
        )
        def synthetic_retrieval_mount(project_id: str, run_id: str) -> None:
            del project_id, run_id
        @retrieval_cancel_router.post(
            "/api/v1/projects/{project_id}/retrieval-runs/{run_id}:cancel",
            status_code=204,
        )
        def synthetic_retrieval_cancel_mount(
            project_id: str, run_id: str,
        ) -> None:
            del project_id, run_id
        @validation_router.post(
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
            "{plan_version_id}:validate",
            status_code=204,
        )
        def synthetic_plan_validation_mount(
            project_id: str, plan_id: str, plan_version_id: str,
        ) -> None:
            del project_id, plan_id, plan_version_id
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())) as license_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                   return_value=Mock()) as write_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                    return_value=Mock()) as upload_issuer_factory, patch(
                    "plm_assistant.entrypoints.production_login.create_windows_ai_egress_router",
                    return_value=egress_router) as egress_factory, patch(
                    "plm_assistant.entrypoints.production_login.create_windows_rag_retrieval_api",
                    return_value=Mock(
                        router=retrieval_router,
                        cancel_router=retrieval_cancel_router,
                        cancellation_owner=retrieval_cancel_owner,
                    )) as retrieval_factory, patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_plan_version_validation_composition",
                    return_value=(validation_router, validation_service),
                    ) as validation_factory, patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_plan_version_review_submission_router",
                    return_value=plan_submit_router,
                    ) as plan_submit_router_factory, patch(
                    "plm_assistant.entrypoints.production_login."
                    "create_windows_plan_version_create_router",
                    return_value=plan_version_create_router,
                    ) as plan_version_create_factory:
            app = create_production_platform_write_app(settings)
        license_factory.assert_called_once()
        write_factory.assert_called_once()
        upload_issuer_factory.assert_called_once()
        egress_factory.assert_called_once()
        retrieval_factory.assert_called_once()
        validation_factory.assert_called_once()
        for name in ("runtime", "sessions", "origins", "license_guard", "audit",
                     "documents", "downloads", "parse_results"):
            self.assertIsNotNone(validation_factory.call_args.kwargs[name])
        self.assertEqual(settings.data_root,
                         validation_factory.call_args.kwargs["document_storage_root"])
        self.assertEqual(settings.data_root,
                         validation_factory.call_args.kwargs["parse_result_storage_root"])
        plan_submit_router_factory.assert_called_once()
        self.assertIs(plan_submit_router_factory.call_args.kwargs[
            "validation_service"], validation_service)
        self.assertTrue(any(
            getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
            "{plan_version_id}:validate"
            and "POST" in getattr(route, "methods", ())
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", ())
        ))
        plan_version_create_factory.assert_called_once()
        for name in ("runtime", "sessions", "origins", "license_guard", "audit",
                     "document_storage_root", "parse_result_storage_root",
                     "documents", "downloads", "parse_results"):
            self.assertIsNotNone(plan_version_create_factory.call_args.kwargs[name])
        self.assertTrue(any(
            getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions"
            and "POST" in getattr(route, "methods", ())
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", ())
        ))
        self.assertIn(
            "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
            "{plan_version_id}:submit-review", app.openapi()["paths"])
        self.handover_action_factory.assert_called_once()
        self.handover_action_write_factory.assert_called_once()
        self.requirement_factory.assert_called_once()
        self.assertTrue(
            self.requirement_factory.call_args.kwargs["include_write"]
        )
        self.prototype_factory.assert_called_once()
        self.assertTrue(
            self.prototype_factory.call_args.kwargs["include_write"]
        )
        self.project_review_factory.assert_called_once()
        self.project_review_read_factory.assert_called_once()
        self.project_review_list_factory.assert_called_once()
        outline_owner = self.project_review_read_factory.call_args.kwargs["outline_subject"]
        self.assertIs(type(outline_owner), OutlineReviewSubjectOwner)
        self.assertIs(self.project_review_list_factory.call_args.kwargs["outline_subject"],
                      outline_owner)
        self.assertIs(self.project_review_factory.call_args.kwargs["outline_subject"],
                      outline_owner)
        self.assertIs(self.project_review_factory.call_args.kwargs[
            "plan_version_validation"], validation_service)
        self.assertTrue(any(
            getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/solution-outlines/{outline_id}/"
            "versions/{outline_version_id}:submit-review"
            and "POST" in getattr(route, "methods", ())
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", ())
        ))
        self.workflow_checklist_factory.assert_called_once()
        self.workflow_checklist_qualification_factory.assert_called_once()
        self.workflow_transition_factory.assert_called_once()
        self.assertTrue(any(
            getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/solution-sections/{section_id}/"
            "versions/{section_version_id}:submit-review"
            and "POST" in getattr(route, "methods", ())
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", ())
        ))
        included_routes = (
            route
            for included in app.routes
            for route in getattr(
                getattr(included, "original_router", None), "routes", (),
            )
        )
        generic_cancel = next((
            route for route in included_routes
            if getattr(route, "path", "") ==
            "/api/v1/projects/{project_id}/jobs/{job_id}:cancel"
        ), None)
        self.assertIsNotNone(
            generic_cancel,
            "generic Project Job cancel route not mounted",
        )
        dispatcher = inspect.getclosurevars(
            generic_cancel.endpoint,
        ).nonlocals["cancellations"]
        self.assertIs(
            dispatcher._owners[("rag", "RAG_RETRIEVAL")],
            retrieval_cancel_owner,
        )
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans/"
                "00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003:validate").status_code, 204)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans"
            ).status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/plans"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions").status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions/00000000-0000-0000-0000-000000000002:revise"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/global/reference-solutions/"
                "00000000-0000-0000-0000-000000000002:revise"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 403)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-outlines/00000000-0000-0000-0000-000000000002").status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections").status_code, 403)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections/00000000-0000-0000-0000-000000000002/versions"
            ).status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "solution-sections/00000000-0000-0000-0000-000000000002/versions/"
                "00000000-0000-0000-0000-000000000003").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "reference-solutions/00000000-0000-0000-0000-000000000002").status_code, 401)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "global-reference-candidates").status_code, 401)
            self.assertEqual(client.post(
                "/api/v1/global/reference-solutions").status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations:preview"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/global/reference-deidentification-confirmations:lookup-operation"
            ).status_code, 403)
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 403)
            self.assertEqual(client.post("/api/v1/admin/ai/models").status_code, 403)
            self.assertEqual(client.post("/api/v1/admin/ai/models/00000000-0000-0000-0000-000000000001:set-state").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.post("/api/v1/global/document-uploads").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/document-uploads").status_code, 403)
            self.assertEqual(client.put("/api/v1/global/document-uploads/00000000-0000-0000-0000-000000000001/content").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 403)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:rotate"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:disable"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/egress-previews"
            ).status_code, 204)
            self.assertEqual(client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "retrieval-runs/00000000-0000-0000-0000-000000000002"
            ).status_code, 204)
            self.assertEqual(client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/"
                "retrieval-runs/00000000-0000-0000-0000-000000000002:cancel"
            ).status_code, 204)
        runtime.dispose.assert_called_once()

    def test_write_mode_missing_upload_key_disposes_without_publishing(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                   side_effect=RuntimeError("synthetic missing upload key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_write_app(settings)
        self.assertNotIn("synthetic missing upload key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_windows_launcher_write_mode_is_explicit(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv",
             ["serve_windows", str(bootstrap), "--platform-write"]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_platform_write_app",
             return_value="synthetic-write-platform") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.args[0](), "synthetic-write-platform")
            factory.assert_called_once_with(settings)

    def test_windows_launcher_trace_modes_are_explicit(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        for mode, name in (
            ("--platform-trace", "create_production_platform_trace_app"),
            ("--platform-write-trace", "create_production_platform_write_trace_app"),
        ):
            with self.subTest(mode=mode), patch(
                "plm_assistant.entrypoints.serve_windows.sys.platform", "win32",
            ), patch(
                "plm_assistant.entrypoints.serve_windows.sys.argv",
                ["serve_windows", str(bootstrap), mode],
            ), patch(
                "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
                return_value=settings,
            ), patch(
                "plm_assistant.entrypoints.serve_windows.uvicorn.run",
            ) as run, patch(
                "plm_assistant.entrypoints.serve_windows." + name,
                return_value="synthetic-trace-app",
            ) as factory:
                self.assertEqual(serve_windows_main(), 0)
                self.assertEqual(run.call_args.args[0](), "synthetic-trace-app")
                factory.assert_called_once_with(settings)

    def test_trace_mode_requires_dedicated_cursor_and_disposes_runtime(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch(
            "plm_assistant.entrypoints.production_login.read_database_url",
            return_value="postgresql+psycopg://localhost/test",
        ), patch(
            "plm_assistant.entrypoints.production_login.create_database_runtime",
            return_value=runtime,
        ), patch(
            "plm_assistant.entrypoints.production_login._schema_current",
            return_value=True,
        ), patch(
            "plm_assistant.entrypoints.windows_license_runtime."
            "create_windows_license_services",
            return_value=Mock(guard=Mock()),
        ), patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_trace_graph_cursor_codec",
            side_effect=RuntimeError("private graph key missing"),
        ) as failed:
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_trace_app(self.settings(("http://localhost",)))
        failed.assert_called_once()
        self.assertNotIn("private", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_trace_read_mode_mounts_graph_without_changing_legacy_mode(self) -> None:
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec

        settings = self.settings(("http://localhost",))
        path = "/api/v1/projects/00000000-0000-0000-0000-000000000001/trace-graph:upstream"
        with patch(
            "plm_assistant.entrypoints.production_login.read_database_url",
            return_value="postgresql+psycopg://localhost/test",
        ), patch(
            "plm_assistant.entrypoints.production_login._schema_current",
            return_value=True,
        ), patch(
            "plm_assistant.entrypoints.windows_license_runtime."
            "create_windows_license_services",
            return_value=Mock(guard=Mock()),
        ), patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_secret_list_cursor_codec",
            return_value=SecretListCursorCodec(b"q" * 32),
        ), patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_member_cursor_codec",
            return_value=MemberListCursorCodec(b"m" * 32),
        ), patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_project_department_cursor_codec",
            return_value=DepartmentListCursorCodec(b"d" * 32),
        ), patch(
            "plm_assistant.entrypoints.production_login."
            "create_windows_trace_graph_cursor_codec",
            return_value=TraceGraphCursorCodec(b"t" * 32),
        ) as cursor_source, patch(
            "plm_assistant.entrypoints.production_login.create_database_runtime",
        ) as runtime_factory:
            runtime_factory.return_value.is_ready.return_value = True
            legacy = create_production_platform_app(settings)
            self.assertEqual(cursor_source.call_count, 0)
            trace = create_production_platform_trace_app(settings)
            cursor_source.assert_called_once_with()
            with TestClient(legacy, base_url="http://localhost") as old_client:
                self.assertEqual(old_client.get(path).status_code, 404)
            with TestClient(trace, base_url="http://localhost") as trace_client:
                self.assertEqual(trace_client.get(path).status_code, 401)

    def test_write_trace_mode_requests_write_and_graph_composition(self) -> None:
        settings = self.settings(("http://localhost",))
        with patch("plm_assistant.entrypoints.production_login._create_production_app",
                   return_value="synthetic-write-trace") as composition:
            self.assertEqual(create_production_platform_write_trace_app(settings),
                             "synthetic-write-trace")
        composition.assert_called_once_with(
            settings, credential_target="PLMProjectTool/Database",
            include_secret_read=True, include_secret_write=True,
            include_trace_graph=True)


if __name__ == "__main__":
    unittest.main()
