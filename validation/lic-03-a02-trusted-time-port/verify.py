"""Disposable PostgreSQL 18 integration verification for trusted-time port."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.license.application.trusted_time import TrustedTimeError, TrustedTimeStatePort
from plm_assistant.modules.license.infrastructure.trusted_time_integrity import HmacTrustedTimeIntegrity
from plm_assistant.modules.license.infrastructure.trusted_time_repository import SqlAlchemyTrustedTimeRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class SyntheticKeyResolver:
    def resolve_key(self, key_ref: str) -> bytes | None:
        return b"synthetic-test-key-not-for-production" if key_ref == "synthetic-trusted-time" else None


def reject(fn, code: str) -> None:
    try:
        fn()
    except TrustedTimeError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"unsafe trusted-time advancement accepted: {code}")


def main() -> None:
    name = f"lic03a02_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            repo = SqlAlchemyTrustedTimeRepository()
            audit = AuditService(SqlAlchemyAuditRepository())
            port = TrustedTimeStatePort(runtime.unit_of_work, repo,
                                        HmacTrustedTimeIntegrity(SyntheticKeyResolver(), key_ref="synthetic-trusted-time"), audit)
            start = datetime.now(timezone.utc) + timedelta(seconds=10)
            with psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True) as db:
                state_id = db.execute("INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES RETURNING trusted_time_state_id").fetchone()[0]
            trace = uuid.uuid4()
            first = port.advance(candidate=start, expected_version=0, trace_id=trace)
            assert first.state_id == state_id and first.state_version == 1
            assert first.integrity_metadata and "tag" in first.integrity_metadata
            same = port.advance(candidate=start, expected_version=1, trace_id=uuid.uuid4())
            assert same.state_version == 1
            within = port.advance(candidate=start - timedelta(seconds=1), expected_version=1,
                                  rollback_tolerance=timedelta(seconds=2), trace_id=uuid.uuid4())
            assert within.state_version == 1
            reject(lambda: port.advance(candidate=start - timedelta(seconds=3), expected_version=1,
                                        rollback_tolerance=timedelta(seconds=2), trace_id=uuid.uuid4()), "TIME_ROLLBACK")
            reject(lambda: port.advance(candidate=start + timedelta(seconds=1), expected_version=0,
                                        trace_id=uuid.uuid4()), "TRUST_STATE_CONFLICT")

            def race(seconds: int) -> str:
                try:
                    port.advance(candidate=start + timedelta(seconds=seconds), expected_version=1,
                                 trace_id=uuid.uuid4())
                    return "ADVANCED"
                except TrustedTimeError as exc:
                    return exc.code

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(race, (2, 3)))
            assert sorted(outcomes) == ["ADVANCED", "TRUST_STATE_CONFLICT"], outcomes
            with psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True) as db:
                assert db.execute("SELECT state_version FROM plm.lic_trusted_time_states").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_TRUSTED_TIME_CHECK'").fetchone()[0] == 7
                tamper_event = db.execute("INSERT INTO plm.lic_trusted_time_events(event_code,candidate_time,trace_id) VALUES ('ADVANCED',%s,%s) RETURNING trusted_time_event_id", (start + timedelta(seconds=4), uuid.uuid4())).fetchone()[0]
                db.execute("UPDATE plm.lic_trusted_time_states SET last_successful_time=%s,state_version=3,integrity_metadata='{}'::jsonb,last_success_event_ref=%s,updated_at=%s WHERE trusted_time_state_id=%s", (start + timedelta(seconds=4), tamper_event, start + timedelta(seconds=4), state_id))
            reject(lambda: port.advance(candidate=start + timedelta(seconds=5), expected_version=3,
                                        trace_id=uuid.uuid4()), "TRUST_STATE_INVALID")
            with psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True) as db:
                assert db.execute("SELECT state_version FROM plm.lic_trusted_time_states").fetchone()[0] == 3
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_TRUSTED_TIME_CHECK'").fetchone()[0] == 8
                assert db.execute("SELECT count(*) FROM plm.lic_trusted_time_events WHERE event_code='INTEGRITY_REJECTED'").fetchone()[0] == 1
            print("PASS: signed advancement, same-time/tolerance no-write, rollback, stale version, two-worker race, corruption fail-close and durable denial audit")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
