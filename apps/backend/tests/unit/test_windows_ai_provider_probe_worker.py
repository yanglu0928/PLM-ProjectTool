"""Closed startup composition; no network, database, or Provider Key is used."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from plm_assistant.entrypoints import windows_ai_provider_probe_worker as entry
from plm_assistant.modules.ai.application.provider_probe_worker import ProviderProbeOneShotWorker
from plm_assistant.modules.ai.infrastructure.provider_probe_secret_audit import ProviderProbeSecretAccessAudit
from plm_assistant.modules.ai.infrastructure.provider_probe_transport import PinnedHttpsProbeTransport
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class WindowsAIProviderProbeWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.policy = {
            "reference": "endpoint.synthetic.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://probe.example.test/v1/chat/completions",
            "model_key": "synthetic-chat", "data_region": "cn-beijing",
            "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
        }
        self.root = Path(temporary.name)

    def settings(self, *, with_policy=True):
        return BootstrapSettings(data_root=self.root,
            ai_probe_policies=(self.policy,) if with_policy else ())

    def test_non_windows_and_missing_policy_never_open_database(self):
        with patch.object(entry.sys, "platform", "linux"), \
             patch.object(entry, "read_database_url") as read:
            with self.assertRaises(entry.WindowsAIProviderProbeWorkerStartupError):
                entry.create_windows_ai_provider_probe_worker(self.settings())
            read.assert_not_called()
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url") as read:
            with self.assertRaises(entry.WindowsAIProviderProbeWorkerStartupError):
                entry.create_windows_ai_provider_probe_worker(self.settings(with_policy=False))
            read.assert_not_called()

    def test_vault_key_failure_disposes_database_without_running_worker(self):
        database = Mock()
        database.maintenance_admission = object()
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime", return_value=database), \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault:
            vault.return_value.resolve_key.side_effect = RuntimeError("private detail")
            with self.assertRaises(entry.WindowsAIProviderProbeWorkerStartupError) as caught:
                entry.create_windows_ai_provider_probe_worker(self.settings())
            self.assertNotIn("private detail", str(caught.exception))
            database.dispose.assert_called_once()

    def test_owned_sources_and_persistent_audit_are_wired_without_running(self):
        database = Mock()
        database.maintenance_admission = object()
        actor = SimpleNamespace(assert_current=lambda: uuid.uuid4())
        with patch.object(entry.sys, "platform", "win32"), \
             patch.object(entry, "read_database_url", return_value="owned"), \
             patch.object(entry, "create_worker_database_runtime", return_value=database) as runtime, \
             patch.object(entry, "create_windows_worker_license_services",
                          return_value=SimpleNamespace(guard=object())), \
             patch.object(entry, "create_windows_system_actor", return_value=actor), \
             patch.object(entry, "WindowsSecretKeyProvider") as vault, \
             patch.object(ProviderProbeOneShotWorker, "run_once") as run:
            vault.return_value.resolve_key.return_value = b"s" * 32
            db, worker = entry.create_windows_ai_provider_probe_worker(self.settings())
            self.assertIs(db, database)
            self.assertIsInstance(worker, ProviderProbeOneShotWorker)
            self.assertIsInstance(worker._runner._audit_scope, ProviderProbeSecretAccessAudit)
            self.assertIs(worker._runner._audit_scope, worker._runner._secrets._audit)
            self.assertIsInstance(worker._runner._transport, PinnedHttpsProbeTransport)
            self.assertEqual(runtime.call_args.kwargs, {"maintenance_admission": True})
            vault.return_value.resolve_key.assert_called_once_with(entry.SECRET_MASTER_KEY_REF)
            run.assert_not_called()
            database.dispose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
