"""Disposable PG18 proof for internal CapabilityBaseline identity creation."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.license_import_access import (
    SqlAlchemyLicenseImportAccess,
)
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateError,
    CapabilityBaselineCreateService,
    CreateCapabilityBaseline,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef,
    CapabilitySourceValidator,
)
from plm_assistant.modules.capability.infrastructure.baseline_create_repository import (
    SqlAlchemyCapabilityBaselineCreateRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
_create_helpers = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
_schema_helpers = runpy.run_path(str(
    ROOT / "validation" / "cap-01-a02-capability-schema" / "verify.py"
))
connect, seed_user = _create_helpers["connect"], _create_helpers["seed_user"]
Guard, FailedAudit, CSRF = (
    _create_helpers["Guard"], _create_helpers["FailedAudit"], _create_helpers["CSRF"],
)
seed_global_source = _schema_helpers["seed_global_source"]


def expect(code: str, action) -> None:
    try:
        action()
    except CapabilityBaselineCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "cap01a03p01_" + uuid.uuid4().hex[:10]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(
                        db, "Synthetic Capability Admin", "DEPLOYMENT_ADMIN", admin_token,
                    )
                    seed_user(db, "Synthetic Capability Member", "NONE", member_token)
                    _, document_id, document_version_id, _ = seed_global_source(db)
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("""
                            UPDATE plm.doc_file_objects f
                               SET sha256=v.content_sha256
                              FROM plm.doc_document_versions v
                             WHERE v.document_version_id=%s
                               AND f.file_object_id=v.file_object_id
                        """, (document_version_id,))
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    sources=CapabilitySourceValidator(SqlAlchemyDocumentReadRepository()),
                    repository=SqlAlchemyCapabilityBaselineCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = CapabilityBaselineCreateService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )

                source = (CapabilityDocumentRef(document_id, document_version_id),)

                def create(*, token=admin_token, csrf=CSRF, code="PLM.CORE",
                           key=None, target=service):
                    return target.create(CreateCapabilityBaseline(
                        token, csrf, uuid.uuid4(), code, "PLM Core",
                        "Synthetic standard", source, key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(
                    key=first_key, code="PLM.CHANGED",
                ))
                with connect(name) as db:
                    row = db.execute(
                        "SELECT baseline_code,baseline_state,current_approved_version_ref,"
                        "lock_version,source_collection_ref FROM plm.cap_baselines "
                        "WHERE baseline_id=%s", (first.baseline_id,),
                    ).fetchone()
                    assert row[:4] == ("PLM.CORE", "ACTIVE", None, 0), row
                    assert row[4] == first.source_collection_ref
                    assert db.execute(
                        "SELECT count(*) FROM plm.cap_baseline_versions"
                    ).fetchone()[0] == 0
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE "
                        "action='CAP_BASELINE_CREATED' AND target_object_id=%s",
                        (first.baseline_id,),
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                        "operation='V1_CAP_BASELINE_CREATE'"
                    ).fetchone()[0] == 1

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(
                        lambda _: create(key=concurrent_key, code="PLM.CONCURRENT"),
                        range(2),
                    ))
                assert results[0] == results[1]

                failed = CapabilityBaselineCreateService(
                    **kwargs, audit=FailedAudit(),
                )
                rollback_key = str(uuid.uuid4())
                expect("CAPABILITY_UNAVAILABLE", lambda: create(
                    key=rollback_key, code="PLM.ROLLBACK", target=failed,
                ))
                rolled = create(
                    key=rollback_key, code="PLM.ROLLBACK",
                )
                assert rolled.baseline_id not in (
                    first.baseline_id, results[0].baseline_id,
                )

                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",
                        (actor,),
                    )
                expect("AUTH_ACCESS_DENIED", lambda: create(key=first_key))
                print(
                    "CAP_01_A03_P01_BASELINE_CREATE_PASS: admin/CSRF/License, "
                    "GLOBAL source, idempotency/concurrency, Audit rollback, "
                    "DRAFT/approved-zero boundary and revocation verified on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
