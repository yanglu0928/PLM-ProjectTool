"""Disposable PostgreSQL migration, concurrency and fencing proof for Outbox."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure import configuration_orm, idempotency_orm, secret_orm  # noqa: F401
from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import user_orm, session_orm, login_rate_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import installation_orm, validation_orm, trusted_time_orm  # noqa: F401
from plm_assistant.modules.project.infrastructure import orm as project_orm  # noqa: F401
from plm_assistant.modules.document.infrastructure import orm as document_orm  # noqa: F401
from plm_assistant.modules.jobs.infrastructure import orm as job_orm  # noqa: F401
from plm_assistant.modules.jobs.application.outbox import OutboxDeliveryError, OutboxDeliveryService
from plm_assistant.modules.jobs.infrastructure.orm import OutboxConsumptionRow, OutboxEventRow
from plm_assistant.modules.jobs.infrastructure.outbox_repository import SqlAlchemyOutboxDeliveryRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def expect_stale(action) -> None:
    try:
        action()
    except OutboxDeliveryError as exc:
        assert exc.code == "STALE_DELIVERY", exc.code
    else:
        raise AssertionError("stale delivery accepted")


def verify() -> None:
    name = "outbox_" + uuid.uuid4().hex[:12]
    admin = psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    cfg = create_migration_config(url)
    runtime = None
    engine = None
    try:
        command.upgrade(cfg, "20260926_0025")
        engine = create_engine(url)
        event_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO plm.job_outbox_events(event_id,event_type,owner_module,scope,aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id,delivery_state) VALUES (:id,'VERSION_COMMITTED','document','GLOBAL',:id,1,'{}'::jsonb,'first','synthetic','DELIVERING')"), {"id": event_id})
        try:
            command.upgrade(cfg, "20260926_0026")
        except RuntimeError as exc:
            assert "controlled recovery" in str(exc)
        else:
            raise AssertionError("unsafe legacy DELIVERING upgrade accepted")
        with engine.begin() as conn:
            conn.execute(text("UPDATE plm.job_outbox_events SET delivery_state='PENDING' WHERE event_id=:id"), {"id": event_id})
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            assert conn.scalar(text("SELECT max_attempts FROM plm.job_outbox_events WHERE event_id=:id"), {"id": event_id}) == 5
            diffs = compare_metadata(MigrationContext.configure(conn, opts={"include_schemas": True, "compare_type": True, "compare_server_default": True, "include_name": lambda name, type_, parent: name == 'plm' if type_ == 'schema' else parent.get('schema_name') in (None, 'plm')}), Base.metadata)
            assert not [d for d in diffs if not (d[0] == "remove_table" and d[1].name == "alembic_version")], diffs
            try:
                with conn.begin_nested():
                    conn.execute(text("UPDATE plm.job_outbox_events SET delivery_state='DELIVERING' WHERE event_id=:id"), {"id": event_id})
            except Exception:
                pass
            else:
                raise AssertionError("lease-less DELIVERING accepted")
        command.downgrade(cfg, "20260926_0025")
        with engine.begin() as conn:
            assert conn.scalar(text("SELECT count(*) FROM plm.job_outbox_events")) == 1
        command.upgrade(cfg, "head")
        runtime = create_database_runtime(url)
        service = OutboxDeliveryService(unit_of_work=runtime.unit_of_work,
                                        repository=SqlAlchemyOutboxDeliveryRepository())
        barrier = Barrier(2)

        def race(owner: str):
            barrier.wait()
            return service.claim_next(owner_ref=owner, lease_seconds=1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ("worker-a", "worker-b")))
        claims = [("worker-a" if i == 0 else "worker-b", value)
                  for i, value in enumerate(results) if value is not None]
        assert len(claims) == 1, results
        first_owner, first = claims[0]
        assert first.event_id == event_id and first.delivery_token == 1
        service.heartbeat(event_id=event_id, delivery_token=1,
                          owner_ref=first_owner, lease_seconds=1)
        expect_stale(lambda: service.heartbeat(event_id=event_id, delivery_token=1,
                                               owner_ref="intruder", lease_seconds=1))
        time.sleep(1.15)
        second = service.claim_next(owner_ref="worker-c", lease_seconds=10)
        assert second is not None and second.event_id == event_id and second.delivery_token == 2
        expect_stale(lambda: service.acknowledge(event_id=event_id, delivery_token=1,
                                                 owner_ref=first_owner, consumer_id="parser",
                                                 consume=lambda tx, claim: None))
        try:
            service.acknowledge(event_id=event_id, delivery_token=2,
                                owner_ref="worker-c", consumer_id="parser",
                                consume=lambda tx, claim: (_ for _ in ()).throw(RuntimeError("consumer failed")))
        except RuntimeError as exc:
            assert str(exc) == "consumer failed"
        else:
            raise AssertionError("consumer failure accepted")
        with runtime.unit_of_work() as tx:
            assert tx.session.execute(select(OutboxEventRow.delivery_state).where(OutboxEventRow.event_id == event_id)).scalar_one() == "DELIVERING"
            assert tx.session.execute(select(OutboxConsumptionRow).where(OutboxConsumptionRow.event_id == event_id)).scalar_one_or_none() is None
        consumed = []
        assert service.acknowledge(event_id=event_id, delivery_token=2,
                                   owner_ref="worker-c", consumer_id="parser",
                                   consume=lambda tx, claim: consumed.append(claim.event_id))
        assert consumed == [event_id]
        expect_stale(lambda: service.acknowledge(event_id=event_id, delivery_token=2,
                                                 owner_ref="worker-c", consumer_id="parser",
                                                 consume=lambda tx, claim: None))
        retry_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add(OutboxEventRow(event_id=retry_id, event_type="VERSION_COMMITTED", owner_module="document",
                                          scope="GLOBAL", aggregate_ref=retry_id, aggregate_version=1,
                                          payload_refs={}, idempotency_key="retry", trace_id="synthetic", max_attempts=2))
            tx.commit()
        retry = service.claim_next(owner_ref="worker-d", lease_seconds=10)
        assert retry is not None and retry.event_id == retry_id
        assert service.retry_or_dead(event_id=retry_id, delivery_token=retry.delivery_token,
                                     owner_ref="worker-d", error_code="TEMPORARY_FAILURE",
                                     retryable=True) == "RETRY_WAIT"
        last = service.claim_next(owner_ref="worker-e", lease_seconds=10)
        assert last is not None and last.event_id == retry_id and last.delivery_token == 2
        assert service.retry_or_dead(event_id=retry_id, delivery_token=last.delivery_token,
                                     owner_ref="worker-e", error_code="TEMPORARY_FAILURE",
                                     retryable=True) == "DEAD"
        dedupe_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add(OutboxEventRow(event_id=dedupe_id, event_type="VERSION_COMMITTED", owner_module="document",
                                          scope="GLOBAL", aggregate_ref=dedupe_id, aggregate_version=1,
                                          payload_refs={}, idempotency_key="dedupe", trace_id="synthetic", max_attempts=1))
            tx.session.flush()
            tx.session.add(OutboxConsumptionRow(event_id=dedupe_id, consumer_id="parser"))
            tx.commit()
        dedupe = service.claim_next(owner_ref="worker-g", lease_seconds=10)
        assert dedupe is not None and dedupe.event_id == dedupe_id
        try:
            service.acknowledge(event_id=dedupe_id, delivery_token=dedupe.delivery_token,
                                owner_ref="worker-g", consumer_id="other",
                                consume=lambda tx, claim: None)
        except OutboxDeliveryError as exc:
            assert exc.code == "CONSUMER_MISMATCH"
        else:
            raise AssertionError("different consumer accepted")
        assert not service.acknowledge(event_id=dedupe_id, delivery_token=dedupe.delivery_token,
                                       owner_ref="worker-g", consumer_id="parser",
                                       consume=lambda tx, claim: (_ for _ in ()).throw(AssertionError("duplicate side effect")))
        assert service.claim_next(owner_ref="worker-f", lease_seconds=10) is None
        try:
            command.downgrade(cfg, "20260926_0025")
        except RuntimeError as exc:
            assert "history exists" in str(exc)
        else:
            raise AssertionError("delivery history downgrade accepted")
        print("PASS: old-data upgrade/downgrade, ORM parity, unsafe legacy refusal, two-worker claim, takeover/fencing, consumer rollback/dedupe and bounded retry")
    finally:
        if runtime is not None:
            runtime.dispose()
        if engine is not None:
            engine.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
