"""Disposable PostgreSQL 18 activation and replacement verification."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.installation_activation import ActivateLicense, LicenseActivationError, LicenseActivationService
from plm_assistant.modules.license.application.license_validation import LicenseValidationError, VerifiedFullBundleLicense
from plm_assistant.modules.license.application.validation_recording import ValidationRecordingService
from plm_assistant.modules.license.infrastructure.installation_activation_repository import SqlAlchemyLicenseActivationRepository
from plm_assistant.modules.license.infrastructure.validation_recording_repository import SqlAlchemyValidationRecordingRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Validator:
    def __init__(self):
        self.denial = None

    def validate(self, document, **kwargs):
        assert kwargs["expected_public_key_ref"] == "synthetic-release"
        if self.denial:
            raise LicenseValidationError(self.denial)
        now = datetime.now(timezone.utc)
        return VerifiedFullBundleLicense(
            "synthetic", "synthetic", hashlib.sha256(document).digest(), b"a" * 32,
            now - timedelta(days=1), now + timedelta(days=1), now,
        )


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic activation audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic01a04_" + uuid.uuid4().hex[:12]
    token, csrf = b"a" * 32, b"b" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES ('Synthetic Activation Admin','synthetic activation admin','DEPLOYMENT_ADMIN') RETURNING user_id").fetchone()[0]
                credential_id = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
                db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential_id, user_id))
                db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), user_id))
                ids = []
                for number in range(4):
                    document = f"synthetic-signed-candidate-{number}".encode()
                    installation_id = db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('synthetic-release',%s,%s) RETURNING license_installation_id", (user_id, uuid.uuid4())).fetchone()[0]
                    db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (installation_id, document, hashlib.sha256(document).digest()))
                    ids.append(installation_id)
            runtime = create_database_runtime(url)
            try:
                audit = AuditService(SqlAlchemyAuditRepository())
                validator = Validator()
                recorder = ValidationRecordingService(runtime.unit_of_work,
                    SqlAlchemyValidationRecordingRepository(), validator, audit)
                repository = SqlAlchemyLicenseActivationRepository()
                access = SqlAlchemyLicenseImportAccess()

                def service(selected_audit):
                    return LicenseActivationService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        recorder=recorder, repository=repository, audit=selected_audit,
                    )

                def activation_command(index):
                    return ActivateLicense(token, csrf, ids[index], 0, 0, uuid.uuid4())

                first = service(audit).activate_imported(activation_command(0))
                assert first.state_version == 0 and first.superseded_installation_id is None
                second = service(audit).activate_imported(activation_command(1))
                assert second.state_version == 1 and second.superseded_installation_id == ids[0], second
                try:
                    service(FailedAudit()).activate_imported(activation_command(2))
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("activation audit failure was accepted")
                with connect(name) as db:
                    third_event = db.execute("SELECT validation_result_ref FROM plm.lic_installations WHERE license_installation_id=%s", (ids[2],)).fetchone()[0]
                with runtime.unit_of_work() as tx:
                    assert repository.activate(tx, installation_id=ids[2], expected_lock_version=1,
                                               event_id=third_event, trace_id=uuid.uuid4(),
                                               now=datetime.now(timezone.utc)) is None
                validator.denial = "MACHINE_MISMATCH"
                try:
                    service(audit).activate_imported(activation_command(3))
                except LicenseActivationError as exc:
                    assert exc.code == "MACHINE_MISMATCH"
                else:
                    raise AssertionError("denied validation was activated")
                with connect(name) as db:
                    states = db.execute("SELECT license_installation_id,installation_state FROM plm.lic_installations ORDER BY license_installation_id").fetchall()
                    by_id = dict(states)
                    assert [by_id[item] for item in ids] == ["SUPERSEDED", "ACTIVE", "IMPORTED", "IMPORTED"]
                    projection = db.execute("SELECT active_license_ref,validation_code,current_event_ref,state_version FROM plm.lic_validation_states").fetchone()
                    assert projection == (ids[1], "VALID", second.validation_event_id, 1), projection
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_ACTIVATED'").fetchone()[0] == 2
                    assert db.execute("SELECT validation_code FROM plm.lic_validation_events WHERE installation_id=%s", (ids[3],)).fetchone()[0] == "MACHINE_MISMATCH"
                print("PASS: PostgreSQL first activation, replacement, stale-evidence rejection, audit rollback and denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
