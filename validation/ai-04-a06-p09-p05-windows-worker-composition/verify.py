"""Windows 11/PostgreSQL 18 proof for dormant production Worker composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedActor:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id

    def assert_current(self) -> uuid.UUID:
        return self.actor_id


class SyntheticKeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_key(self, key_ref: str) -> bytes:
        assert key_ref == entry.SECRET_MASTER_KEY_REF
        self.calls += 1
        return b"k" * 32


def validate(context: dict[str, object]) -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p09p05_schema_helper",
    )
    with schema.connect(context["database"]) as db:
        task = db.execute(
            "SELECT task_type,prompt_policy_ref,prompt_policy_version,"
            "prompt_template_ref,output_schema_ref,context_policy_ref "
            "FROM plm.ai_tasks WHERE ai_task_id=%s",
            (context["ai_task_id"],),
        ).fetchone()
        route = db.execute(
            "SELECT c.endpoint_policy_ref,c.data_region,c.egress_class,m.provider_model_key "
            "FROM plm.ai_provider_config_versions c JOIN plm.ai_models m "
            "ON m.ai_provider_id=c.ai_provider_id WHERE c.config_version_no=1",
        ).fetchone()
        username = "worker-composition-system-" + uuid.uuid4().hex[:12]
        actor_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
        before = db.execute(
            "SELECT (SELECT count(*) FROM plm.ai_invocations),"
            "(SELECT count(*) FROM plm.aud_events "
            "WHERE action='SECRET_ACCESSED')",
        ).fetchone()
    assert task is not None and route is not None
    settings = BootstrapSettings(
        data_root=context["result_root"],
        ai_task_policies=({
            "reference": task[1], "policy_version": task[2],
            "task_type": task[0], "prompt_template_id": str(task[3]),
            "purpose_ref": "project-gap-analysis.v1",
            "output_schema_ref": task[4], "context_policy_ref": task[5],
            "parameter_fields": [{
                "name": "language", "value_type": "STRING",
                "required": True, "max_length": 16,
                "minimum": None, "maximum": None,
                "allowed_values": [],
            }],
        },),
        ai_execution_policies=({
            "reference": route[0], "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://api.example.test/v1/chat/completions",
            "data_region": route[1], "egress_class": route[2],
            "allowed_model_keys": [route[3]],
            "max_response_bytes": 1_000_000,
            "connect_timeout_seconds": 3,
            "read_timeout_seconds": 10,
            "total_timeout_seconds": 20,
        },),
    )
    key_provider = SyntheticKeyProvider()
    database = None
    with patch.object(entry, "read_database_url", return_value=context["url"]), \
         patch.object(
             entry, "create_windows_worker_license_services",
             return_value=SimpleNamespace(guard=context["guard"]),
         ), \
         patch.object(entry, "create_windows_system_actor",
                      return_value=FixedActor(actor_id)), \
         patch.object(entry, "WindowsSecretKeyProvider",
                      return_value=key_provider), \
         patch.object(PinnedHttpsOpenAICompatibleAdapter, "send") as send:
        database, loop = entry.create_windows_ai_provider_loop(settings)
        assert database.is_ready()
        assert isinstance(loop, AIProviderCombinedWorkerLoop)
        assert isinstance(loop._task, AIBusinessTaskOneShotWorker)
        assert isinstance(loop._probe, entry._IdleProbeWorker)
        assert loop._admission is database.maintenance_admission
        assert loop._task._sender._audit_scope is loop._task._sender._secrets._audit
        send.assert_not_called()
    assert key_provider.calls == 1
    if database is not None:
        database.dispose()
    with schema.connect(context["database"]) as db:
        after = db.execute(
            "SELECT (SELECT count(*) FROM plm.ai_invocations),"
            "(SELECT count(*) FROM plm.aud_events "
            "WHERE action='SECRET_ACCESSED')",
        ).fetchone()
    assert before == after == (0, 0)
    print(
        "AI_04_A06_P09_P05_WINDOWS_WORKER_COMPOSITION_PASS: Windows11/"
        "PostgreSQL18.6 strict non-secret business execution policy assembled "
        "the owner-specific business Worker, bounded HTTPS Adapter, encrypted "
        "Secret boundary, expired reconciler and combined loop under one real "
        "Worker database/admission runtime; startup performed zero claim, zero "
        "Invocation, zero Provider Secret access and zero Provider network I/O"
    )


def main() -> None:
    composition = load_helper(
        "ai-04-a06-p04-p04-a06-windows-composition", "p09p05_composition",
    )
    composition.main(after_validation=validate)


if __name__ == "__main__":
    main()
