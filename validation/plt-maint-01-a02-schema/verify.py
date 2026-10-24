"""Disposable PG18 proof for CR-PLT-004 singleton state migration."""

from __future__ import annotations

import os
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.maintenance_orm import MaintenanceStateRow
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def url_for(name):
    return URL.create("postgresql+psycopg", username="poc_admin",
                      host="127.0.0.1", port=PORT, database=name)


def reject(db, statement):
    before = tuple(db.execute("SELECT * FROM plm.plt_maintenance_state"))
    try:
        db.execute(statement)
    except psycopg.Error:
        pass
    else:
        raise AssertionError("invalid maintenance state mutation accepted")
    assert tuple(db.execute("SELECT * FROM plm.plt_maintenance_state")) == before


def verify():
    names = ["plt_maint_empty_" + uuid.uuid4().hex[:9],
             "plt_maint_data_" + uuid.uuid4().hex[:9]]
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            empty, populated = (create_migration_config(url_for(name)) for name in names)
            command.upgrade(empty, "head")
            with connect(names[0]) as db:
                assert tuple(db.execute("SELECT state_id,state,lock_version FROM "
                    "plm.plt_maintenance_state")) == ((1, "RUNNING", 0),)
            command.downgrade(empty, "20260930_0050")
            command.upgrade(empty, "head")

            command.upgrade(populated, "20260930_0050")
            with connect(names[1]) as db:
                actor = db.execute("INSERT INTO plm.auth_users("
                    "username_display,username_normalized) VALUES "
                    "('Maintenance Seed','maintenance seed') RETURNING user_id").fetchone()[0]
            command.upgrade(populated, "head")
            with connect(names[1]) as db:
                assert db.execute("SELECT user_id FROM plm.auth_users "
                    "WHERE user_id=%s", (actor,)).fetchone()[0] == actor
                assert tuple(db.execute("SELECT state_id,state,lock_version FROM "
                    "plm.plt_maintenance_state")) == ((1, "RUNNING", 0),)
                reject(db, "INSERT INTO plm.plt_maintenance_state("
                    "state_id,state,lock_version,changed_at) VALUES "
                    "(2,'RUNNING',0,clock_timestamp())")
                reject(db, "UPDATE plm.plt_maintenance_state SET "
                    "state='MAINTENANCE',lock_version=2")
                reject(db, "UPDATE plm.plt_maintenance_state SET "
                    "state='RUNNING',lock_version=1")
                reject(db, "DELETE FROM plm.plt_maintenance_state")
                reject(db, "TRUNCATE plm.plt_maintenance_state")
                db.execute("UPDATE plm.plt_maintenance_state SET "
                    "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                assert db.execute("SELECT state,lock_version FROM "
                    "plm.plt_maintenance_state").fetchone() == ("MAINTENANCE", 1)
                db.execute("UPDATE plm.plt_maintenance_state SET "
                    "state='RUNNING',lock_version=2 WHERE state_id=1")
                assert db.execute("SELECT state,lock_version FROM "
                    "plm.plt_maintenance_state").fetchone() == ("RUNNING", 2)
            try:
                command.downgrade(populated, "20260930_0050")
            except Exception:
                pass
            else:
                raise AssertionError("maintenance history downgrade accepted")
            with connect(names[1]) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version"
                    ).fetchone()[0] == "20260930_0051"
                assert db.execute("SELECT state,lock_version FROM "
                    "plm.plt_maintenance_state").fetchone() == ("RUNNING", 2)
            engine = create_engine(url_for(names[1]))
            try:
                with engine.connect() as connection:
                    columns = inspect(connection).get_columns(
                        MaintenanceStateRow.__tablename__, schema="plm")
                    assert set(column["name"] for column in columns) == set(
                        MaintenanceStateRow.__table__.c.keys())
                    assert all(not column["nullable"] for column in columns)
            finally:
                engine.dispose()
            print("PLT-MAINT-01-A02 PASS: empty and populated PG18 up/down/up, "
                  "ORM parity, singleton/transition guards, historical down rejected")
        finally:
            for name in names:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
