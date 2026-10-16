"""Owned disposable DB only; reason history, not real customer/Owner approval."""
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import uuid
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository

spec = spec_from_file_location("_reason_fixture", Path(__file__).resolve().parents[1] / "rvw-01-a02-review-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    name = "reviewreason_"+uuid.uuid4().hex[:12]
    engine = None
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0034")
            with fixture.connect(name) as db:
                actor, reviewer = [fixture.insert(db, "auth_users", dict(username_display=f"Synthetic reason {i}",
                    username_normalized=f"synthetic reason {i}"), "user_id") for i in range(2)]
                project = fixture.insert(db, "prj_projects", dict(project_code="REASON", project_code_normalized="reason",
                    name="Synthetic reason history", created_by=actor), "project_id")
                review = fixture.review(db, actor, project)
                with db.transaction():
                    old_round, _, _ = fixture.start(db, review, actor, (reviewer,))
                    fixture.withdraw(db, old_round, actor)
                old = fixture.snapshot(db)
            command.upgrade(config, "head")
            command.check(config)
            engine = create_engine(url)
            repository = SqlAlchemyReviewSnapshotReadRepository()
            def get(round_id):
                with Session(engine) as session, session.begin():
                    return repository.get_round(SimpleNamespace(session=session), "PROJECT", project, review, round_id)
            with fixture.connect(name) as db:
                # All old event fields retained verbatim; only appended NULL.
                after = fixture.snapshot(db)
                for index, (before_rows, after_rows) in enumerate(zip(old, after)):
                    if index == 7:
                        assert [row[:-1] for row in after_rows] == before_rows
                        assert all(row[-1] is None for row in after_rows)
                    else:
                        assert after_rows == before_rows
                assert get(old_round).progress.withdrawal.reason is None
            command.downgrade(config, "20260926_0034")
            command.upgrade(config, "head")
            with fixture.connect(name) as db:
                def withdraw_reason(reason):
                    round_id, _, _ = fixture.start(db, review, actor, (reviewer,))
                    fixture.withdraw(db, round_id, actor, omit="event")
                    fixture.insert(db, "rvw_round_events", dict(review_id=review, review_round_id=round_id,
                        scope="PROJECT", project_id=project, event_type="WITHDRAWN", actor_id=actor,
                        trace_id=uuid.uuid4(), occurred_at=datetime.now(timezone.utc), before_lock_version=0,
                        after_lock_version=1, result_state="WITHDRAWN", decision_id=None,
                        withdrawal_reason=reason), "round_event_id")
                    return round_id
                for invalid in ("", " ", "\t\n"):
                    fixture.reject(db, lambda invalid=invalid: withdraw_reason(invalid))
                with db.transaction():
                    new_round = withdraw_reason("合成测试：范围调整，请重新送审。")
                assert get(new_round).progress.withdrawal.reason == "合成测试：范围调整，请重新送审。"
                assert get(old_round).progress.withdrawal.reason is None
                fixture.reject(db, lambda: db.execute("UPDATE plm.rvw_round_events SET withdrawal_reason='changed' WHERE review_round_id=%s", (new_round,)))
                def wrong_event_reason():
                    round_id, _, _ = fixture.start(db, review, actor, (reviewer,), omit="event")
                    fixture.insert(db, "rvw_round_events", dict(review_id=review, review_round_id=round_id,
                        scope="PROJECT", project_id=project, event_type="STARTED", actor_id=actor,
                        trace_id=uuid.uuid4(), occurred_at=datetime.now(timezone.utc), before_lock_version=None,
                        after_lock_version=0, result_state="IN_REVIEW", decision_id=None,
                        withdrawal_reason="not withdrawal"), "round_event_id")
                fixture.reject(db, wrong_event_reason)
                retained = fixture.snapshot(db)
            try:
                command.downgrade(config, "20260926_0034")
            except RuntimeError as exc:
                assert "reason history exists" in str(exc)
            else:
                raise AssertionError("reason loss downgrade accepted")
            with fixture.connect(name) as db:
                assert fixture.snapshot(db) == retained
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260926_0035"
            command.check(config)
            print("RVW-02-A07 PASS: empty/existing upgrade/down/re-up, ORM, legacy NULL/history, Chinese reason read, immutable/events rejection, loss-prevention down; synthetic subjects only")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
