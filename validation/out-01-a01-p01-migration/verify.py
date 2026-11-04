"""Verify OUT-01 schema migrations against isolated PostgreSQL 18 databases."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import errors, sql
from sqlalchemy import URL, create_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.platform.infrastructure.migration import (  # noqa: E402
    downgrade_database,
    upgrade_database,
)
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime  # noqa: E402
from plm_assistant.modules.plugin.application.operation_capability import (  # noqa: E402
    PluginOperationCapabilityReader,
)
from plm_assistant.modules.plugin.application.signature_verifier import (  # noqa: E402
    TrustedPluginSigner,
)
from plm_assistant.modules.plugin.infrastructure.operation_capability_repository import (  # noqa: E402
    SqlAlchemyPluginOperationCapabilityRepository,
)
from plm_assistant.modules.plugin.infrastructure.packaged_signer_resolver import (  # noqa: E402
    PackagedPluginSignerResolver,
)
from plm_assistant.modules.output.infrastructure.plugin_operation_registry_adapter import (  # noqa: E402
    PluginOperationRegistryAdapter,
)


def _database_url(name: str, port: int) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username="postgres",
        host="127.0.0.1",
        port=port,
        database=name,
    )


def _dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(sql.Identifier(name))
        )


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def _revision(dsn: str) -> str:
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT version_num FROM plm.alembic_version").fetchone()
        if row is None:
            raise AssertionError("database has no Alembic revision")
        return row[0]


def _assert_output_tables(dsn: str, expected: bool) -> None:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT to_regclass('plm.out_context_snapshots'), "
            "to_regclass('plm.out_output_requests')"
        ).fetchone()
    actual = all(rows)
    if actual is not expected:
        raise AssertionError(f"Output table presence mismatch: {rows!r}")


def _assert_plugin_installation_tables(dsn: str, expected: bool) -> None:
    tables = ("plg_installations", "plg_enabled_operations", "plg_runtime_validations", "plg_enabled_operation_history")
    with psycopg.connect(dsn) as conn:
        found = [conn.execute("SELECT to_regclass(%s)", ("plm." + name,)).fetchone()[0]
                 for name in tables]
    if (all(found)) is not expected or (not expected and any(found)):
        raise AssertionError(f"PluginInstallation table presence mismatch: {found!r}")
    if expected:
        _assert_plugin_installation_contract(dsn)


def _assert_plugin_installation_contract(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        owner_closed, no_truncate, immutable = conn.execute(
            "SELECT "
            "(SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN "
            "('trg_plg_installations__owner_closed','trg_plg_enabled_operations__owner_closed',"
            "'trg_plg_runtime_validations__owner_closed','trg_plg_enabled_operation_history__owner_closed')),"
            "(SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN "
            "('trg_plg_installations__no_truncate','trg_plg_enabled_operations__no_truncate',"
            "'trg_plg_runtime_validations__no_truncate','trg_plg_enabled_operation_history__no_truncate')),"
            "(SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
            "AND tgname IN ('trg_plg_runtime_validations__immutable','trg_plg_enabled_operation_history__immutable'))"
        ).fetchone()
        fk_count = conn.execute(
            "SELECT count(*) FROM pg_constraint WHERE contype='f' AND conname IN "
            "('fk_plg_installations__package_plugin',"
            "'fk_plg_enabled_operations__installation_package',"
            "'fk_plg_enabled_operations__manifest_operation',"
            "'fk_plg_runtime_validations__installation','fk_plg_enabled_operation_history__installation','fk_plg_enabled_operation_history__manifest_operation','fk_plg_enabled_operation_history__audit_event')"
        ).fetchone()[0]
        unique_index = conn.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname='plm' "
            "AND indexname='uq_plg_enabled_operations__plugin_operation'"
        ).fetchone()[0]
    if owner_closed != 4 or no_truncate != 4 or immutable != 2:
        raise AssertionError(
            "PluginInstallation trigger contract mismatch: "
            f"owner_closed={owner_closed}, no_truncate={no_truncate}, immutable={immutable}"
        )
    if fk_count != 7 or unique_index != 1:
        raise AssertionError(
            f"PluginInstallation relation contract mismatch: fk={fk_count}, unique_index={unique_index}"
        )

    for table in ("plg_installations", "plg_enabled_operations", "plg_runtime_validations", "plg_enabled_operation_history"):
        with psycopg.connect(dsn) as conn:
            try:
                with conn.transaction():
                    conn.execute(sql.SQL("INSERT INTO plm.{} DEFAULT VALUES").format(
                        sql.Identifier(table)
                    ))
            except errors.RaiseException:
                pass
            else:
                raise AssertionError(f"closed PluginInstallation Owner accepted INSERT on {table}")

    for table in ("plg_enabled_operations", "plg_runtime_validations"):
        with psycopg.connect(dsn) as conn:
            try:
                with conn.transaction():
                    conn.execute(sql.SQL("TRUNCATE plm.{}").format(sql.Identifier(table)))
            except errors.RaiseException:
                pass
            else:
                raise AssertionError(f"PluginInstallation Owner allowed TRUNCATE on {table}")

    with psycopg.connect(dsn) as conn:
        try:
            with conn.transaction():
                conn.execute(
                    "TRUNCATE plm.plg_installations, plm.plg_enabled_operations, "
                    "plm.plg_runtime_validations, plm.plg_enabled_operation_history, "
                    "plm.plg_disable_results"
                )
        except errors.RaiseException:
            pass
        else:
            raise AssertionError("PluginInstallation Owner allowed grouped TRUNCATE")


def _seed_plugin_installation_history(dsn: str, package_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    installation_ids = (uuid.uuid4(), uuid.uuid4())
    actor_id = uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "SELECT set_config('plm.plugin_installation_owner_write', 'on', true)"
        )
        for installation_id in installation_ids:
                conn.execute(
                    "INSERT INTO plm.plg_installations "
                    "(plugin_installation_id,plugin_package_id,plugin_id_normalized,"
                    "installation_state,validated_runtime_snapshot,installed_by,"
                    "created_by,updated_by,lock_version) "
                    "VALUES (%s,%s,'synthetic.upgrade','INSTALLED',"
                    "'{\"schema_version\":\"1\",\"source\":\"test-only\"}'::jsonb,"
                    "%s,%s,%s,0)",
                    (installation_id, package_id, actor_id, actor_id, actor_id),
                )
        conn.execute(
            "ALTER TABLE plm.plg_enabled_operations "
            "DISABLE TRIGGER trg_plg_enabled_operations__owner_closed"
        )
        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO plm.plg_enabled_operations "
                    "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
                    "VALUES (%s,'document.render',%s,'synthetic.wrong')",
                    (installation_ids[0], package_id),
                )
        except errors.ForeignKeyViolation:
            pass
        else:
            raise AssertionError("installation/package composite FK accepted mismatched plugin id")

        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO plm.plg_enabled_operations "
                    "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
                    "VALUES (%s,'missing.operation',%s,'synthetic.upgrade')",
                    (installation_ids[0], package_id),
                )
        except errors.ForeignKeyViolation:
            pass
        else:
            raise AssertionError("enabled operation FK accepted a missing manifest operation")

        conn.execute(
            "INSERT INTO plm.plg_enabled_operations "
            "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
            "VALUES (%s,'document.render',%s,'synthetic.upgrade')",
            (installation_ids[0], package_id),
        )
        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO plm.plg_enabled_operations "
                    "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
                    "VALUES (%s,'document.render',%s,'synthetic.upgrade')",
                    (installation_ids[1], package_id),
                )
        except errors.UniqueViolation:
            pass
        else:
            raise AssertionError("enabled operation uniqueness did not span installations")
        conn.execute(
            "ALTER TABLE plm.plg_enabled_operations "
            "ENABLE TRIGGER trg_plg_enabled_operations__owner_closed"
        )

        conn.execute(
            "SELECT set_config('plm.plugin_installation_owner_write', 'on', true)"
        )
        audit_id = conn.execute(
            "INSERT INTO plm.aud_events "
            "(trace_id,event_scope,actor_type,actor_id,action,outcome,"
            "target_owner_module,target_object_type,target_object_id,before_state,after_state) "
            "VALUES (%s,'DEPLOYMENT','USER',%s,'PLUGIN_OPERATION_ENABLE','SUCCESS',"
            "'plugin','PLG-02',%s,'INSTALLED','ENABLED') RETURNING audit_event_id",
            (uuid.uuid4(), actor_id, installation_ids[0]),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO plm.plg_enabled_operation_history "
            "(plugin_installation_id,plugin_package_id,plugin_id_normalized,operation_id,"
            "transition,actor_id,trace_id,audit_event_id) "
            "VALUES (%s,%s,'synthetic.upgrade','document.render','ENABLED',%s,%s,%s)",
            (installation_ids[0], package_id, actor_id, uuid.uuid4(), audit_id),
        )
        conn.execute(
            "INSERT INTO plm.plg_runtime_validations "
                "(plugin_installation_id,compatibility_state,runtime_snapshot,validated_by) "
                "VALUES (%s,'COMPATIBLE',"
                "'{\"schema_version\":\"1\",\"source\":\"test-only\"}'::jsonb,%s)",
                (installation_ids[0], actor_id),
            )
        incompatible_snapshot = '{"schema_version":"1","source":"test-incompatible"}'
        conn.execute(
            "INSERT INTO plm.plg_runtime_validations "
            "(plugin_installation_id,compatibility_state,runtime_snapshot,validated_by) "
            "VALUES (%s,'INCOMPATIBLE',%s::jsonb,%s)",
            (installation_ids[0], incompatible_snapshot, actor_id),
        )
        conn.execute(
            "DELETE FROM plm.plg_enabled_operations "
            "WHERE plugin_installation_id=%s AND operation_id='document.render'",
            (installation_ids[0],),
        )
        disabled_audit_id = conn.execute(
            "INSERT INTO plm.aud_events "
            "(trace_id,event_scope,actor_type,actor_id,action,outcome,"
            "target_owner_module,target_object_type,target_object_id,before_state,after_state) "
            "VALUES (%s,'DEPLOYMENT','USER',%s,'PLUGIN_OPERATION_DISABLE','SUCCESS',"
            "'plugin','PLG-02',%s,'ENABLED','INCOMPATIBLE') RETURNING audit_event_id",
            (uuid.uuid4(), actor_id, installation_ids[0]),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO plm.plg_enabled_operation_history "
            "(plugin_installation_id,plugin_package_id,plugin_id_normalized,operation_id,"
            "transition,actor_id,trace_id,audit_event_id) "
            "VALUES (%s,%s,'synthetic.upgrade','document.render','DISABLED',%s,%s,%s)",
            (installation_ids[0], package_id, actor_id, uuid.uuid4(), disabled_audit_id),
        )
        conn.execute(
            "UPDATE plm.plg_installations SET installation_state='INCOMPATIBLE',"
            "validated_runtime_snapshot=%s::jsonb,updated_by=%s,"
            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
            "WHERE plugin_installation_id=%s",
            (incompatible_snapshot, actor_id, installation_ids[0]),
        )
    return installation_ids




def _seed_plugin_operation_capability(dsn: str, package_id: uuid.UUID) -> uuid.UUID:
    """Create synthetic current Plugin facts for the hosted P11 read-only query."""
    installation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    snapshot = {
        "schema_version": "1",
        "os": "windows-11",
        "architecture": "x86_64",
        "python_version": "3.13.15",
        "dependency_versions": {},
    }
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "SELECT set_config('plm.plugin_installation_owner_write', 'on', true)"
        )
        conn.execute(
            "INSERT INTO plm.plg_package_verifications "
            "(plugin_package_id,verification_state,check_code,summary) "
            "VALUES (%s,'PASSED','SIGNED_PACKAGE_VALID',"
            "'synthetic hosted P11 fixture only')",
            (package_id,),
        )
        conn.execute(
            "INSERT INTO plm.plg_installations "
            "(plugin_installation_id,plugin_package_id,plugin_id_normalized,"
            "installation_state,validated_runtime_snapshot,installed_by,"
            "created_by,updated_by,enabled_by,enabled_at,lock_version) "
            "VALUES (%s,%s,'synthetic.upgrade','ENABLED',%s::jsonb,%s,%s,%s,%s,"
            "statement_timestamp(),0)",
            (installation_id, package_id, json.dumps(snapshot), actor_id,
             actor_id, actor_id, actor_id),
        )
        conn.execute(
            "INSERT INTO plm.plg_enabled_operations "
            "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
            "VALUES (%s,'document.render',%s,'synthetic.upgrade')",
            (installation_id, package_id),
        )
        conn.execute(
            "INSERT INTO plm.plg_runtime_validations "
            "(plugin_installation_id,compatibility_state,runtime_snapshot,validated_by) "
            "VALUES (%s,'COMPATIBLE',%s::jsonb,%s)",
            (installation_id, json.dumps(snapshot), actor_id),
        )
    return installation_id


class _SyntheticP11SignerResolver:
    def resolve_trusted_signer(self, signer_key_ref: str):
        if signer_key_ref != "synthetic-upgrade-key":
            return None
        return TrustedPluginSigner(
            signer_key_ref=signer_key_ref,
            public_key_raw=bytes([0x42]) * 32,
            state="ACTIVE",
        )


def _verify_plugin_operation_capability(
    database_url: URL, dsn: str, installation_id: uuid.UUID,
) -> None:
    synthetic_runtime = DatabaseRuntime(create_engine(database_url))
    try:
        adapter = PluginOperationRegistryAdapter(
            PluginOperationCapabilityReader(
                SqlAlchemyPluginOperationCapabilityRepository(
                    _SyntheticP11SignerResolver(),
                ),
            ),
        )
        with synthetic_runtime.unit_of_work() as transaction:
            capability = adapter.get_operation(
                transaction, operation_id="document.render",
            )
        if (capability is None or capability.output_types != ("DOCX",)
                or capability.enabled is not True or capability.trusted is not True):
            raise AssertionError("P11 complete synthetic capability did not resolve")
    finally:
        synthetic_runtime.dispose()

    production_runtime = DatabaseRuntime(create_engine(database_url))
    try:
        production_adapter = PluginOperationRegistryAdapter(
            PluginOperationCapabilityReader(
                SqlAlchemyPluginOperationCapabilityRepository(
                    PackagedPluginSignerResolver(),
                ),
            ),
        )
        with production_runtime.unit_of_work() as transaction:
            production_capability = production_adapter.get_operation(
                transaction, operation_id="document.render",
            )
        if (production_capability is None or production_capability.enabled is not True
                or production_capability.trusted is not False):
            raise AssertionError(
                "P11 empty packaged publisher registry did not fail closed"
            )
    finally:
        production_runtime.dispose()

    incompatible = {
        "schema_version": "1",
        "os": "windows-11",
        "architecture": "x86_64",
        "python_version": "3.13.15",
        "dependency_versions": {},
    }
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "SELECT set_config('plm.plugin_installation_owner_write', 'on', true)"
        )
        conn.execute(
            "INSERT INTO plm.plg_runtime_validations "
            "(plugin_installation_id,compatibility_state,runtime_snapshot,validated_by) "
            "VALUES (%s,'INCOMPATIBLE',%s::jsonb,%s)",
            (installation_id, json.dumps(incompatible), uuid.uuid4()),
        )
    runtime = DatabaseRuntime(create_engine(database_url))
    try:
        reader = PluginOperationCapabilityReader(
            SqlAlchemyPluginOperationCapabilityRepository(
                _SyntheticP11SignerResolver(),
            ),
        )
        with runtime.unit_of_work() as transaction:
            stale = reader.get_operation(
                transaction, operation_id="document.render",
            )
        if stale is None or stale.enabled is not False or stale.trusted is not True:
            raise AssertionError("P11 latest incompatible RuntimeValidation was ignored")
    finally:
        runtime.dispose()

    duplicate_package_id = uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO plm.plg_packages "
            "(plugin_package_id,plugin_id_normalized,plugin_version,package_sha256,"
            "manifest_snapshot,signature,signer_key_ref,compatibility_policy_ref) "
            "VALUES (%s,'synthetic.ambiguous','1.0.0',%s,"
            "'{\"schema_version\":\"1\"}'::jsonb,%s,'unknown-test-key',"
            "'host.platforms.v1')",
            (duplicate_package_id, bytes([0x55]) * 32, bytes([0x66]) * 64),
        )
        conn.execute(
            "INSERT INTO plm.plg_manifest_operations "
            "(plugin_package_id,operation_id,output_types,plugin_api_version) "
            "VALUES (%s,'document.render','[\"DOCX\"]'::jsonb,'1')",
            (duplicate_package_id,),
        )
    ambiguity_runtime = DatabaseRuntime(create_engine(database_url))
    try:
        reader = PluginOperationCapabilityReader(
            SqlAlchemyPluginOperationCapabilityRepository(
                _SyntheticP11SignerResolver(),
            ),
        )
        with ambiguity_runtime.unit_of_work() as transaction:
            ambiguous = reader.get_operation(
                transaction, operation_id="document.render",
            )
        if ambiguous is not None:
            raise AssertionError("P11 ambiguous operation definitions did not fail closed")
    finally:
        ambiguity_runtime.dispose()

def _verify_plugin_retirement_guard(dsn: str, installation_id: uuid.UUID) -> None:
    actor_id = uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "SELECT set_config('plm.plugin_installation_owner_write', 'on', true)"
        )
        conn.execute("SAVEPOINT retirement_without_audit")
        try:
            conn.execute(
                "UPDATE plm.plg_installations SET installation_state='RETIRED',"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 "
                "WHERE plugin_installation_id=%s",
                (actor_id, installation_id),
            )
        except errors.RaiseException:
            conn.execute("ROLLBACK TO SAVEPOINT retirement_without_audit")
        else:
            raise AssertionError("retirement Owner guard accepted a missing AuditEvent")
        conn.execute("RELEASE SAVEPOINT retirement_without_audit")
        audit_id = conn.execute(
            "INSERT INTO plm.aud_events "
            "(trace_id,event_scope,actor_type,actor_id,action,outcome,"
            "target_owner_module,target_object_type,target_object_id,reason_code,"
            "before_state,after_state) "
            "VALUES (%s,'DEPLOYMENT','USER',%s,'PLUGIN_INSTALLATION_RETIRE','SUCCESS',"
            "'plugin','PLG-02',%s,'INSTALLATION_RETIRED','INSTALLED','RETIRED') "
            "RETURNING audit_event_id",
            (uuid.uuid4(), actor_id, installation_id),
        ).fetchone()[0]
        if audit_id is None:
            raise AssertionError("retirement AuditEvent was not persisted")
        row = conn.execute(
            "UPDATE plm.plg_installations SET installation_state='RETIRED',"
            "updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 "
            "WHERE plugin_installation_id=%s RETURNING installation_state,lock_version",
            (actor_id, installation_id),
        ).fetchone()
        if row != ("RETIRED", 1):
            raise AssertionError(f"Installation retirement transition mismatch: {row!r}")
        conn.execute("SAVEPOINT terminal_retirement")
        try:
            conn.execute(
                "UPDATE plm.plg_installations SET installation_state='DISABLED',"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 "
                "WHERE plugin_installation_id=%s",
                (actor_id, installation_id),
            )
        except errors.RaiseException:
            conn.execute("ROLLBACK TO SAVEPOINT terminal_retirement")
        else:
            raise AssertionError("retired Installation accepted a state transition")
        conn.execute("RELEASE SAVEPOINT terminal_retirement")
        final = conn.execute(
            "SELECT installation_state,lock_version FROM plm.plg_installations "
            "WHERE plugin_installation_id=%s",
            (installation_id,),
        ).fetchone()
        if final != ("RETIRED", 1):
            raise AssertionError("retirement guard changed terminal state after rejected write")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("migration validation requires a loopback port and numeric run id")

    suffix = args.run_id[-10:]
    empty_db = f"plm_out01_{suffix}_empty"
    existing_db = f"plm_out01_{suffix}_existing"
    admin_dsn = _dsn("postgres", args.port)
    created: list[str] = []
    result = {
        "status": "PASS_LIMITED",
        "postgresql_version": None,
        "empty_database_upgrade": "PENDING",
        "owner_migration_downgrade_reupgrade": "PENDING",
        "empty_database_downgrade_reupgrade": "PENDING",
        "existing_synthetic_data_upgrade": "PENDING",
        "installation_constraints": "PENDING",
        "installation_history_blocks_downgrade": "PENDING",
        "customer_data": False,
        "external_api_calls": 0,
        "production_database": False,
    }
    try:
        with psycopg.connect(admin_dsn) as conn:
            result["postgresql_version"] = conn.execute(
                "SELECT current_setting('server_version')"
            ).fetchone()[0]
        _create_database(admin_dsn, empty_db)
        created.append(empty_db)
        empty_url = _database_url(empty_db, args.port)
        empty_dsn = _dsn(empty_db, args.port)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261104_0230":
            raise AssertionError("empty upgrade did not reach schema head")
        _assert_output_tables(empty_dsn, True)
        _assert_plugin_installation_tables(empty_dsn, True)
        result["empty_database_upgrade"] = "PASS"

        downgrade_database(empty_url, "20261102_0220")
        if _revision(empty_dsn) != "20261102_0220":
            raise AssertionError("owner downgrade did not stop at the Output foundation")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
        if closed != 2 or job_fk != 0: raise AssertionError("0221 downgrade contract mismatch")
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261104_0230": raise AssertionError("owner re-upgrade failed")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
            immutable = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname='trg_out_context_snapshots__immutable'").fetchone()[0]
        if closed != 0 or job_fk != 1 or immutable != 1: raise AssertionError("0221 upgrade contract mismatch")
        result["owner_migration_downgrade_reupgrade"] = "PASS"
        downgrade_database(empty_url, "20261026_0210")
        if _revision(empty_dsn) != "20261026_0210": raise AssertionError("P01 downgrade failed")
        _assert_output_tables(empty_dsn, False)
        _assert_plugin_installation_tables(empty_dsn, False)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261104_0230": raise AssertionError("full re-upgrade failed")
        _assert_output_tables(empty_dsn, True)
        _assert_plugin_installation_tables(empty_dsn, True)
        result["empty_database_downgrade_reupgrade"] = "PASS"

        _create_database(admin_dsn, existing_db)
        created.append(existing_db)
        existing_url = _database_url(existing_db, args.port)
        existing_dsn = _dsn(existing_db, args.port)
        upgrade_database(existing_url, "20261026_0210")
        with psycopg.connect(existing_dsn) as conn:
            existing_maintenance = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
        if existing_maintenance is None:
            raise AssertionError("prior migration did not create its expected maintenance singleton")
        upgrade_database(existing_url, "20261103_0224")
        package_id = __import__("uuid").uuid4()
        with psycopg.connect(existing_dsn) as conn:
            conn.execute(
                "INSERT INTO plm.plg_packages "
                "(plugin_package_id,plugin_id_normalized,plugin_version,package_sha256,"
                "manifest_snapshot,signature,signer_key_ref,compatibility_policy_ref,"
                "package_state,verified_at,created_at,lock_version) "
                "VALUES (%s,'synthetic.upgrade','1.0.0',%s,'{\"schema_version\":\"1\"}'::jsonb,"
                "%s,'synthetic-upgrade-key','host.platforms.v1','VERIFIED',"
                "statement_timestamp(),statement_timestamp(),0)",
                (package_id, bytes([0x21]) * 32, bytes([0x31]) * 64),
            )
            conn.execute(
                "INSERT INTO plm.plg_manifest_operations "
                "(plugin_package_id,operation_id,output_types,plugin_api_version) "
                "VALUES (%s,'document.render','[\"DOCX\"]'::jsonb,'1')",
                (package_id,),
            )
        upgrade_database(existing_url, "head")
        if _revision(existing_dsn) != "20261104_0230":
            raise AssertionError("existing database upgrade did not reach schema head")
        _assert_output_tables(existing_dsn, True)
        _assert_plugin_installation_tables(existing_dsn, True)
        with psycopg.connect(existing_dsn) as conn:
            row = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
            retained = conn.execute(
                "SELECT (SELECT count(*) FROM plm.plg_packages WHERE plugin_package_id=%s),"
                "(SELECT count(*) FROM plm.plg_manifest_operations WHERE plugin_package_id=%s)",
                (package_id, package_id),
            ).fetchone()
        if row != existing_maintenance:
            raise AssertionError("pre-existing synthetic data changed during migration")
        if retained != (1, 1):
            raise AssertionError("pre-existing PLG-01 package facts changed during migration")
        result["existing_synthetic_data_upgrade"] = "PASS"

        installation_ids = _seed_plugin_installation_history(existing_dsn, package_id)
        result["installation_constraints"] = "PASS"
        _verify_plugin_retirement_guard(existing_dsn, installation_ids[1])
        result["installation_retirement_guard"] = "PASS"
        history_query = (
            "SELECT (SELECT count(*) FROM plm.plg_installations),"
            "(SELECT count(*) FROM plm.plg_enabled_operations),"
            "(SELECT count(*) FROM plm.plg_runtime_validations),"
            "(SELECT count(*) FROM plm.plg_enabled_operation_history)"
        )
        with psycopg.connect(existing_dsn) as conn:
            history_before = conn.execute(history_query).fetchone()
        if history_before != (2, 0, 2, 2):
            raise AssertionError(
                f"PLG-02 incompatibility fixture shape changed: {history_before!r}"
            )
        try:
            downgrade_database(existing_url, "20261104_0226")
        except RuntimeError as exc:
            if "PluginInstallation runtime history prevents downgrade" not in str(exc):
                raise
        else:
            raise AssertionError("PLG-02 migration allowed downgrade with installation history")
        if _revision(existing_dsn) != "20261104_0230":
            raise AssertionError("blocked PluginInstallation downgrade changed migration revision")
        with psycopg.connect(existing_dsn) as conn:
            history_after = conn.execute(history_query).fetchone()
            installation_count = conn.execute(
                "SELECT count(*) FROM plm.plg_installations "
                "WHERE plugin_installation_id IN (%s,%s)",
                installation_ids,
            ).fetchone()[0]
        if history_after != history_before or installation_count != 2:
            raise AssertionError(
                "blocked PluginInstallation downgrade changed existing history: "
                f"before={history_before!r}; after={history_after!r}"
            )
        result["installation_history_blocks_downgrade"] = "PASS"
        capability_installation = _seed_plugin_operation_capability(
            existing_dsn, package_id,
        )
        _verify_plugin_operation_capability(
            existing_url, existing_dsn, capability_installation,
        )
        result["plugin_operation_capability"] = "PASS_LIMITED"
    finally:
        for name in reversed(created):
            _drop_database(admin_dsn, name)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
