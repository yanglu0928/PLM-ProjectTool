"""Disposable PG18 proof for complete immutable DRAFT Capability Version."""

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
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateService, CreateCapabilityBaseline,
)
from plm_assistant.modules.capability.application.create_version import (
    CapabilityItemDraft, CapabilityVersionCreateError,
    CapabilityVersionCreateService, CreateCapabilityVersion,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef, CapabilitySourceValidator,
)
from plm_assistant.modules.capability.infrastructure.baseline_create_repository import (
    SqlAlchemyCapabilityBaselineCreateRepository,
)
from plm_assistant.modules.capability.infrastructure.version_create_repository import (
    SqlAlchemyCapabilityVersionCreateRepository,
)
from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionValidationError, CapabilityVersionValidationService,
    ValidateCapabilityVersion,
)
from plm_assistant.modules.capability.infrastructure.version_validation_repository import (
    SqlAlchemyCapabilityVersionValidationRepository,
)
from plm_assistant.modules.audit.infrastructure.capability_validation_source import (
    SqlAlchemyCapabilityValidationAuditSource,
)
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
_create = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
_schema = runpy.run_path(str(ROOT / "validation" / "cap-01-a02-capability-schema" / "verify.py"))
connect, seed_user = _create["connect"], _create["seed_user"]
Guard, FailedAudit, CSRF = _create["Guard"], _create["FailedAudit"], _create["CSRF"]
seed_global_source = _schema["seed_global_source"]


def expect(code: str, action) -> None:
    try:
        action()
    except CapabilityVersionCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "cap01a03p02_" + uuid.uuid4().hex[:10]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=55434, database=name)
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Version Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Version Member", "NONE", member_token)
                    _, document_id, document_version_id, evidence_id = seed_global_source(db)
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("""
                            UPDATE plm.doc_file_objects f SET sha256=v.content_sha256
                              FROM plm.doc_document_versions v
                             WHERE v.document_version_id=%s
                               AND f.file_object_id=v.file_object_id
                        """, (document_version_id,))
                guard = Guard()
                documents = SqlAlchemyDocumentReadRepository()
                sources = CapabilitySourceValidator(documents)
                receipts = SqlAlchemyIdempotencyReceipts()
                audit = AuditService(SqlAlchemyAuditRepository())
                access = SqlAlchemyLicenseImportAccess()
                baseline_service = CapabilityBaselineCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, sources=sources,
                    repository=SqlAlchemyCapabilityBaselineCreateRepository(),
                    receipts=receipts, audit=audit,
                    clock=lambda: datetime.now(timezone.utc),
                )
                source = (CapabilityDocumentRef(document_id, document_version_id),)
                baseline = baseline_service.create(CreateCapabilityBaseline(
                    admin_token, CSRF, uuid.uuid4(), "PLM.CORE", "PLM Core",
                    "Synthetic standard", source, str(uuid.uuid4()),
                ))
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, sources=sources,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    repository=SqlAlchemyCapabilityVersionCreateRepository(),
                    receipts=receipts, clock=lambda: datetime.now(timezone.utc),
                )
                service = CapabilityVersionCreateService(**kwargs, audit=audit)
                validation = CapabilityVersionValidationService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, sources=sources,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    repository=SqlAlchemyCapabilityVersionValidationRepository(),
                    audit_source=SqlAlchemyCapabilityValidationAuditSource(),
                    receipts=receipts, audit=audit,
                    clock=lambda: datetime.now(timezone.utc),
                )
                stable_item_id = uuid.uuid4()

                def create(*, token=admin_token, csrf=CSRF, expected=0,
                           key=None, code="PLM.DOCUMENT.VERSION", target=service):
                    item = CapabilityItemDraft(
                        stable_item_id, code, "PLM", "Document", "Versioning",
                        "Document versioning", "Immutable document versions",
                        "GLOBAL standards only", ("PostgreSQL 18",),
                        ("DOC-V1",), "AVAILABLE", source, (evidence_id,),
                    )
                    return target.create(CreateCapabilityVersion(
                        token, csrf, uuid.uuid4(), baseline.baseline_id,
                        expected, (item,), key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True
                expect("CONFLICT_VERSION", lambda: create(expected=1))

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(
                    key=first_key, code="PLM.CHANGED",
                ))
                assert first.version_no == 1 and first.supersedes_version_ref is None
                assert first.lock_version == 1

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(
                        lambda _: create(expected=1, key=concurrent_key,
                                         code="PLM.DOCUMENT.VERSION2"),
                        range(2),
                    ))
                assert results[0] == results[1]
                assert results[0].version_no == 2
                assert results[0].supersedes_version_ref == first.baseline_version_id
                assert results[0].lock_version == 2

                failed = CapabilityVersionCreateService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("CAPABILITY_UNAVAILABLE", lambda: create(
                    expected=2, key=rollback_key,
                    code="PLM.DOCUMENT.VERSION3", target=failed,
                ))
                third = create(expected=2, key=rollback_key,
                               code="PLM.DOCUMENT.VERSION3")
                assert third.version_no == 3 and third.lock_version == 3

                def validate(version_id, key):
                    return validation.validate(ValidateCapabilityVersion(
                        admin_token, CSRF, uuid.uuid4(), baseline.baseline_id,
                        version_id, key,
                    ))

                passed = validate(first.baseline_version_id, str(uuid.uuid4()))
                assert passed.valid and passed.issue_codes == ()
                invalid_key = str(uuid.uuid4())
                with connect(name) as db, db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute("UPDATE plm.evd_evidence_records SET "
                               "eligibility_state='CANDIDATE',eligibility_reason=NULL "
                               "WHERE evidence_id=%s",
                               (evidence_id,))
                invalid = validate(third.baseline_version_id, invalid_key)
                assert not invalid.valid and invalid.issue_codes == ("EVIDENCE_UNAVAILABLE",)
                with connect(name) as db, db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute("UPDATE plm.evd_evidence_records SET "
                               "eligibility_state='ELIGIBLE',"
                               "eligibility_reason='restored synthetic source' "
                               "WHERE evidence_id=%s",
                               (evidence_id,))
                assert validate(third.baseline_version_id, invalid_key) == invalid
                assert validate(third.baseline_version_id, str(uuid.uuid4())).valid

                with connect(name) as db:
                    assert db.execute(
                        "SELECT lock_version,current_approved_version_ref FROM "
                        "plm.cap_baselines WHERE baseline_id=%s", (baseline.baseline_id,),
                    ).fetchone() == (3, None)
                    counts = db.execute("""
                        SELECT (SELECT count(*) FROM plm.cap_baseline_versions),
                               (SELECT count(*) FROM plm.cap_items),
                               (SELECT count(*) FROM plm.cap_item_document_refs),
                               (SELECT count(*) FROM plm.cap_item_evidence_refs)
                    """).fetchone()
                    assert counts == (3, 3, 3, 3), counts
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE "
                        "action='CAP_VERSION_CREATED'"
                    ).fetchone()[0] == 3
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                        "operation='V1_CAP_VERSION_CREATE'"
                    ).fetchone()[0] == 3
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE "
                        "action='CAP_VERSION_VALIDATED'"
                    ).fetchone()[0] == 3
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                        "operation='V1_CAP_VERSION_VALIDATE'"
                    ).fetchone()[0] == 3
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",
                               (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: create(key=first_key))
                try:
                    command.downgrade(cfg, "20261005_0091")
                except Exception as error:
                    assert "Capability history prevents downgrade" in str(error), str(error)
                else:
                    raise AssertionError("Schema0092 downgrade accepted Version history")
                print(
                    "CAP_01_A03_P02_VERSION_CREATE_PASS: complete DRAFT snapshots, "
                    "Document/Evidence sources, ETag/version sequence, idempotency/"
                    "concurrency, Audit rollback and retained-history guard verified"
                )
                print(
                    "CAP_01_A03_P03_VERSION_VALIDATE_PASS: current PASS/invalid "
                    "reports, immutable Audit replay and no state transition verified"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
