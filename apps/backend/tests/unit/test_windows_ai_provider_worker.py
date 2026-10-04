"""Unified Windows AI Provider role assembles no network work at startup."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from plm_assistant.entrypoints import windows_ai_provider_worker as entry
from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskOneShotWorker,
)
from plm_assistant.modules.ai.application.provider_combined_worker_loop import (
    AIProviderCombinedWorkerLoop,
)
from plm_assistant.modules.ai.infrastructure.openai_compatible_adapter import (
    PinnedHttpsOpenAICompatibleAdapter,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)


class WindowsAIProviderWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task_policy = {
            "reference": "gap-analysis.v1", "policy_version": 1,
            "task_type": "GAP_ANALYSIS",
            "prompt_template_id": str(uuid.uuid4()),
            "purpose_ref": "project-gap-analysis.v1",
            "output_schema_ref": "gap-output.v1",
            "context_policy_ref": "no-retrieval.v1",
            "parameter_fields": [{
                "name": "language", "value_type": "STRING",
                "required": True, "max_length": 16,
                "minimum": None, "maximum": None,
                "allowed_values": [],
            }],
        }
        self.execution_policy = {
            "reference": "endpoint.business.v1",
            "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://business.example.test/v1/chat/completions",
            "data_region": "cn-beijing",
            "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
            "allowed_model_keys": ["business-chat"],
            "max_response_bytes": 1048576,
            "connect_timeout_seconds": 5,
            "read_timeout_seconds": 30,
            "total_timeout_seconds": 40,
        }
        self.probe_policy = {
            "reference": "endpoint.probe.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://probe.example.test/v1/chat/completions",
            "model_key": "business-chat", "data_region": "cn-beijing",
            "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
        }
        self.retrieval_policy = {
            "reference": "fts.project.v1", "scope": "PROJECT",
            "rerank_policy_ref": "none.v1",
            "context_policy_ref": "project-documents.v1",
        }

    def settings(self, *, probe=False, tasks=True, execution=True,
                 retrieval=False):
        return BootstrapSettings(
            data_root=self.root,
            ai_probe_policies=(self.probe_policy,) if probe else (),
            ai_task_policies=(self.task_policy,) if tasks else (),
            ai_execution_policies=(self.execution_policy,) if execution else (),
            rag_retrieval_policies=(self.retrieval_policy,) if retrieval else (),
        )

    def test_retrieval_only_reuses_role_without_provider_master_key(self):
        database = Mock()
        database.maintenance_admission = SimpleNamespace(admit=Mock())
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        retrieval = SimpleNamespace(
            worker=Mock(run_once=Mock()),
            terminal_reconciler=Mock(reconcile_expired_next=Mock()),
            cancel_reconciler=Mock(reconcile_expired_next=Mock()),
        )
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime",
                          return_value=database), \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault, \
             patch.object(entry, "create_windows_rag_retrieval_worker",
                          return_value=retrieval) as factory:
            owned, loop = entry.create_windows_ai_provider_loop(self.settings(
                tasks=False, execution=False, retrieval=True,
            ))
        self.assertIs(owned, database)
        self.assertIsInstance(loop, AIProviderCombinedWorkerLoop)
        self.assertIs(loop._retrieval, retrieval.worker)
        self.assertIsInstance(loop._task, entry._IdleTaskWorker)
        factory.assert_called_once()
        vault.return_value.resolve_key.assert_not_called()

    def test_non_windows_empty_and_incomplete_policy_never_open_database(self):
        cases = (
            ("linux", self.settings()),
            ("win32", self.settings(tasks=False, execution=False)),
            ("win32", self.settings(tasks=True, execution=False)),
            ("win32", self.settings(tasks=False, execution=True)),
            ("win32", BootstrapSettings(
                data_root=self.root,
                ai_task_policies=({
                    **self.task_policy,
                    "context_policy_ref": "project-documents.v1",
                },),
                ai_execution_policies=(self.execution_policy,),
            )),
        )
        for platform, settings in cases:
            with self.subTest(platform=platform, tasks=bool(settings.ai_task_policies),
                              execution=bool(settings.ai_execution_policies)), \
                    patch.object(entry.sys, "platform", platform), \
                    patch.object(entry, "read_database_url") as read:
                with self.assertRaises(entry.WindowsAIProviderWorkerStartupError):
                    entry.create_windows_ai_provider_loop(settings)
                read.assert_not_called()

    def test_probe_only_preserves_existing_composition(self):
        expected = (object(), object())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "create_windows_ai_provider_probe_loop",
                          return_value=expected) as legacy:
            actual = entry.create_windows_ai_provider_loop(
                self.settings(probe=True, tasks=False, execution=False),
            )
        self.assertIs(actual, expected)
        legacy.assert_called_once()

    def test_business_only_wires_combined_loop_without_running_or_network(self):
        database = Mock()
        database.maintenance_admission = SimpleNamespace(admit=Mock())
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime",
                          return_value=database) as runtime, \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault, \
             patch.object(AIBusinessTaskOneShotWorker, "run_once") as task_run, \
             patch.object(PinnedHttpsOpenAICompatibleAdapter, "send") as send:
            vault.return_value.resolve_key.return_value = b"m" * 32
            owned, loop = entry.create_windows_ai_provider_loop(self.settings())
        self.assertIs(owned, database)
        self.assertIsInstance(loop, AIProviderCombinedWorkerLoop)
        self.assertIsInstance(loop._task, AIBusinessTaskOneShotWorker)
        self.assertIsInstance(loop._probe, entry._IdleProbeWorker)
        self.assertIs(loop._admission, database.maintenance_admission)
        self.assertIsInstance(
            loop._task._sender._audit_scope, AITaskProviderSecretAccessAudit,
        )
        self.assertIs(
            loop._task._sender._audit_scope,
            loop._task._sender._secrets._audit,
        )
        self.assertIsInstance(
            loop._task._sender._adapter,
            PinnedHttpsOpenAICompatibleAdapter,
        )
        self.assertTrue(loop._task_ref.startswith("ai-task-"))
        self.assertTrue(loop._probe_ref.startswith("ai-probe-"))
        runtime.assert_called_once_with("owned", maintenance_admission=True)
        vault.return_value.resolve_key.assert_called_once_with(
            entry.SECRET_MASTER_KEY_REF,
        )
        task_run.assert_not_called()
        send.assert_not_called()
        database.dispose.assert_not_called()

    def test_probe_and_business_are_distinct_workers_in_one_loop(self):
        database = Mock()
        database.maintenance_admission = SimpleNamespace(admit=Mock())
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime",
                          return_value=database), \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault:
            vault.return_value.resolve_key.return_value = b"m" * 32
            _, loop = entry.create_windows_ai_provider_loop(
                self.settings(probe=True),
            )
        self.assertIsInstance(loop, AIProviderCombinedWorkerLoop)
        self.assertIsInstance(loop._probe, entry.ProviderProbeOneShotWorker)
        self.assertIsInstance(loop._task, AIBusinessTaskOneShotWorker)
        self.assertIsNot(
            loop._probe._runner._transport,
            loop._task._sender._adapter,
        )

    def test_startup_failure_disposes_owned_database_and_hides_detail(self):
        database = Mock()
        database.maintenance_admission = SimpleNamespace(admit=Mock())
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime",
                          return_value=database), \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault:
            vault.return_value.resolve_key.side_effect = RuntimeError(
                "private vault detail",
            )
            with self.assertRaises(entry.WindowsAIProviderWorkerStartupError) as error:
                entry.create_windows_ai_provider_loop(self.settings())
        self.assertNotIn("private vault detail", str(error.exception))
        database.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
