"""Windows 11/PostgreSQL 18 proof for the fair combined Provider loop."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text

from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskWorkerCycle,
)
from plm_assistant.modules.ai.application.provider_combined_worker_loop import (
    AIProviderCombinedWorkerLoop,
)
from plm_assistant.modules.ai.application.provider_probe_worker import (
    ProviderProbeWorkerCycle,
)
from plm_assistant.modules.ai.application.reconcile_expired_task import (
    ExpiredAITaskReconciler,
)
from plm_assistant.modules.ai.infrastructure.expired_task_reconciliation_repository import (
    SqlAlchemyExpiredAITaskReconciliationRepository,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY,
    PostgresMaintenanceAdmission,
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


class LockCheckingTaskWorker:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.states = ["SUCCEEDED", "FAILED"]
        self.calls = 0

    def run_once(self, *, worker_ref: str) -> AIBusinessTaskWorkerCycle:
        assert worker_ref == "combined-business-proof"
        assert_shared_admission(self.engine)
        self.calls += 1
        state = self.states.pop(0)
        return AIBusinessTaskWorkerCycle(
            state, uuid.uuid4(),
            uuid.uuid4() if state == "SUCCEEDED" else None,
            "SYNTHETIC_FAILURE" if state == "FAILED" else None,
        )


class LockCheckingProbeWorker:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.states = ["SUCCEEDED", "RETRY_WAIT"]
        self.calls = 0

    def run_once(self, *, worker_ref: str) -> ProviderProbeWorkerCycle:
        assert worker_ref == "combined-probe-proof"
        assert_shared_admission(self.engine)
        self.calls += 1
        state = self.states.pop(0)
        return ProviderProbeWorkerCycle(
            state, uuid.uuid4(),
            uuid.uuid4() if state == "SUCCEEDED" else None,
        )


def assert_shared_admission(engine) -> None:
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": MAINTENANCE_LOCK_KEY},
        )
        if acquired is True:
            connection.scalar(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": MAINTENANCE_LOCK_KEY},
            )
            connection.commit()
        assert acquired is False


def validate(context: dict[str, object]) -> None:
    p03 = load_helper(
        "ai-04-a06-p09-p03-business-one-shot", "p09p04_p03_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p09p04_schema_helper",
    )
    p03.validate(context)
    username = "combined-loop-system-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        actor_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]

    engine = create_engine(
        context["url"], pool_pre_ping=True, hide_parameters=True,
    )
    try:
        task = LockCheckingTaskWorker(engine)
        probe = LockCheckingProbeWorker(engine)
        loop = AIProviderCombinedWorkerLoop(
            probe_worker=probe, probe_worker_ref="combined-probe-proof",
            task_worker=task, task_worker_ref="combined-business-proof",
            reconciler=ExpiredAITaskReconciler(
                unit_of_work=context["runtime"].unit_of_work,
                store=SqlAlchemyExpiredAITaskReconciliationRepository(),
                audit=AuditService(SqlAlchemyAuditRepository()),
                system_actor=FixedActor(actor_id),
            ),
            maintenance_admission=PostgresMaintenanceAdmission(engine),
            poll_seconds=.05, max_reconciliations_per_cycle=1,
        )
        result = loop.run(max_cycles=4)
        assert result.reason == "LIMIT" and result.cycles == 4
        assert result.reconciled == 0
        assert (
            result.task_succeeded, result.task_failed,
            result.probe_succeeded, result.probe_retry_wait,
        ) == (1, 1, 1, 1)
        assert task.calls == probe.calls == 2
        with loop.quiescent():
            with engine.connect() as connection:
                acquired = connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": MAINTENANCE_LOCK_KEY},
                )
                assert acquired is True
                released = connection.scalar(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": MAINTENANCE_LOCK_KEY},
                )
                connection.commit()
                assert released is True
    finally:
        engine.dispose()
    print(
        "AI_04_A06_P09_P04_COMBINED_WORKER_LOOP_PASS: Windows11/"
        "PostgreSQL18.6 real maintenance shared admission covered bounded expired "
        "Task reconciliation and alternating business/probe cycles; both busy "
        "families executed 2/2 without starvation, exclusive maintenance was "
        "blocked during work and available after quiescence; prior real business "
        "one-shot chain remained PASS, zero real Provider network or customer data "
        "egress"
    )


def main() -> None:
    composition = load_helper(
        "ai-04-a06-p04-p04-a06-windows-composition", "p09p04_composition",
    )
    composition.main(after_validation=validate)


if __name__ == "__main__":
    main()
