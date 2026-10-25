"""Disposable PostgreSQL 18 transaction check for LIC-02-A03."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.license.application.license_validation import LicenseValidationError, VerifiedFullBundleLicense
from plm_assistant.modules.license.application.validation_recording import ValidationRecordingService
from plm_assistant.modules.license.infrastructure.validation_recording_repository import SqlAlchemyValidationRecordingRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Validator:
    def __init__(self):
        self.denial = None

    def validate(self, document, **kwargs):
        if self.denial:
            raise LicenseValidationError(self.denial)
        assert kwargs["expected_public_key_ref"] == "synthetic-release"
        now = datetime.now(timezone.utc)
        return VerifiedFullBundleLicense("synthetic", "synthetic", hashlib.sha256(document).digest(),
                                         b"a" * 32, now, now, now)


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic02a03_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            document = b"synthetic-not-a-real-license"
            with connect(name) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Recorder','synthetic recorder') RETURNING user_id").fetchone()[0]
                installation_id = db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('synthetic-release',%s,%s) RETURNING license_installation_id", (user_id, uuid.uuid4())).fetchone()[0]
                db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (installation_id, document, hashlib.sha256(document).digest()))
            runtime = create_database_runtime(url)
            try:
                validator = Validator()
                repository = SqlAlchemyValidationRecordingRepository()
                service = ValidationRecordingService(runtime.unit_of_work, repository, validator,
                                                     AuditService(SqlAlchemyAuditRepository()))
                first = service.record_imported(installation_id, expected_lock_version=0,
                                                expected_time_version=0, trace_id=uuid.uuid4())
                assert first.code == "VALID" and first.lock_version == 1
                validator.denial = "SIGNATURE_INVALID"
                second = service.record_imported(installation_id, expected_lock_version=1,
                                                 expected_time_version=0, trace_id=uuid.uuid4())
                assert second.code == "SIGNATURE_INVALID" and second.lock_version == 2
                failing = ValidationRecordingService(runtime.unit_of_work, repository, validator, FailedAudit())
                try:
                    failing.record_imported(installation_id, expected_lock_version=2,
                                            expected_time_version=0, trace_id=uuid.uuid4())
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("audit failure was accepted")
                with connect(name) as db:
                    row = db.execute("SELECT installation_state,validation_result_ref,lock_version FROM plm.lic_installations WHERE license_installation_id=%s", (installation_id,)).fetchone()
                    assert row == ("IMPORTED", second.event_id, 2), row
                    events = db.execute("SELECT validation_code FROM plm.lic_validation_events ORDER BY validated_at").fetchall()
                    assert len(events) == 2 and {r[0] for r in events} == {"VALID", "SIGNATURE_INVALID"}
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_VALIDATION_RECORDED'").fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.lic_validation_states").fetchone()[0] == 0
                print("PASS: PostgreSQL event/pointer/audit atomicity, denial, rollback and no activation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
