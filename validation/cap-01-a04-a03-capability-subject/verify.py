"""Disposable PG18 proof for the real Capability Review Subject start lock."""

from __future__ import annotations

import runpy
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.current_user_access import (
    SqlAlchemyCurrentUserAccess,
)
from plm_assistant.modules.auth.infrastructure.license_import_access import (
    SqlAlchemyLicenseImportAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateService,
    CreateCapabilityBaseline,
)
from plm_assistant.modules.capability.application.create_version import (
    CapabilityItemDraft,
    CapabilityVersionCreateError,
    CapabilityVersionCreateService,
    CreateCapabilityVersion,
)
from plm_assistant.modules.capability.application.review_subject import (
    CapabilityReviewSubjectOwner,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityReadError, CapabilityReadQuery, CapabilityReadService,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef,
    CapabilitySourceValidator,
)
from plm_assistant.modules.capability.infrastructure.baseline_create_repository import (
    SqlAlchemyCapabilityBaselineCreateRepository,
)
from plm_assistant.modules.capability.infrastructure.review_subject_repository import (
    SqlAlchemyCapabilityReviewSubjectRepository,
)
from plm_assistant.modules.capability.infrastructure.version_create_repository import (
    SqlAlchemyCapabilityVersionCreateRepository,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.infrastructure.capability_read_access import (
    SqlAlchemyCapabilityReadMembership,
)
from plm_assistant.modules.review.application.global_persistence import (
    GlobalReviewPersistenceService,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.global_repository import (
    SqlAlchemyGlobalReviewRepository,
)


ROOT = Path(__file__).resolve().parents[2]
_create = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
_schema = runpy.run_path(str(
    ROOT / "validation" / "cap-01-a02-capability-schema" / "verify.py"
))
connect, seed_user = _create["connect"], _create["seed_user"]
Guard, CSRF = _create["Guard"], _create["CSRF"]
seed_global_source = _schema["seed_global_source"]


def main() -> None:
    terminal_enabled = os.environ.get("PLM_CAP_TERMINAL_VALIDATION") == "1"
    read_enabled = os.environ.get("PLM_CAP_READ_VALIDATION") == "1"
    name = "cap01a04a03_" + uuid.uuid4().hex[:10]
    admin_token = b"a" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            if terminal_enabled:
                command.downgrade(cfg, "20261005_0093")
                command.upgrade(cfg, "head")
                command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(
                        db, "Synthetic Subject Admin", "DEPLOYMENT_ADMIN",
                        admin_token,
                    )
                    reviewer_one = seed_user(
                        db, "Synthetic Subject Reviewer One", "NONE",
                        b"b" * 32,
                    )
                    reviewer_two = seed_user(
                        db, "Synthetic Subject Reviewer Two", "NONE",
                        b"c" * 32,
                    )
                    _, document_id, document_version_id, evidence_id = (
                        seed_global_source(db)
                    )
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("""
                            UPDATE plm.doc_file_objects f
                               SET sha256=v.content_sha256
                              FROM plm.doc_document_versions v
                             WHERE v.document_version_id=%s
                               AND f.file_object_id=v.file_object_id
                        """, (document_version_id,))
                now = datetime.now(timezone.utc)
                guard = Guard()
                sources = CapabilitySourceValidator(
                    SqlAlchemyDocumentReadRepository()
                )
                evidence = SqlAlchemyEvidenceFixedSourceRepository()
                receipts = SqlAlchemyIdempotencyReceipts()
                audit = AuditService(SqlAlchemyAuditRepository())
                access = SqlAlchemyLicenseImportAccess()
                source = (CapabilityDocumentRef(
                    document_id, document_version_id,
                ),)
                baseline = CapabilityBaselineCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, sources=sources,
                    repository=SqlAlchemyCapabilityBaselineCreateRepository(),
                    receipts=receipts, audit=audit, clock=lambda: now,
                ).create(CreateCapabilityBaseline(
                    admin_token, CSRF, uuid.uuid4(), "PLM.REVIEW",
                    "PLM Review", "Synthetic review subject", source,
                    str(uuid.uuid4()),
                ))
                item = CapabilityItemDraft(
                    uuid.uuid4(), "PLM.REVIEW.SUBJECT", "PLM", "Review",
                    "Subject", "Review Subject", "Review subject owner",
                    "GLOBAL only", (), (), "AVAILABLE", source,
                    (evidence_id,),
                )
                version_service = CapabilityVersionCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, sources=sources, evidence=evidence,
                    repository=SqlAlchemyCapabilityVersionCreateRepository(),
                    receipts=receipts, audit=audit, clock=lambda: now,
                )
                version = version_service.create(CreateCapabilityVersion(
                    admin_token, CSRF, uuid.uuid4(), baseline.baseline_id, 0,
                    (item,), str(uuid.uuid4()),
                ))
                owner = CapabilityReviewSubjectOwner(
                    users=SqlAlchemyCurrentUserAccess(),
                    repository=SqlAlchemyCapabilityReviewSubjectRepository(),
                    sources=sources, evidence=evidence, audit=audit,
                    terminal_enabled=terminal_enabled, clock=lambda: now,
                )
                review = GlobalReviewPersistenceService(
                    repository=SqlAlchemyGlobalReviewRepository(),
                    audit=audit, subjects=owner, clock=lambda: now,
                )

                with connect(name) as db, db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute("""
                        UPDATE plm.evd_evidence_records
                           SET eligibility_state='CANDIDATE',
                               eligibility_reason=NULL
                         WHERE evidence_id=%s
                    """, (evidence_id,))
                try:
                    with runtime.unit_of_work() as tx:
                        review.submit_in_transaction(
                            tx, actor_id=actor, subject_type="CAP-01",
                            subject_id=baseline.baseline_id,
                            subject_version_id=version.baseline_version_id,
                            reviewer_ids=(reviewer_one, reviewer_two),
                            policy_code="DEPLOYMENT_ALL_V1",
                            trace_id=uuid.uuid4(),
                        )
                        tx.commit()
                except ReviewSubjectAccessDenied:
                    pass
                else:
                    raise AssertionError("invalid Evidence entered Review")
                with connect(name) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.rvw_reviews"
                    ).fetchone()[0] == 0
                    assert db.execute("""
                        SELECT version_state,review_ref,review_round_ref
                          FROM plm.cap_baseline_versions
                         WHERE baseline_version_id=%s
                    """, (version.baseline_version_id,)).fetchone() == (
                        "DRAFT", None, None,
                    )
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("""
                            UPDATE plm.evd_evidence_records
                               SET eligibility_state='ELIGIBLE',
                                   eligibility_reason='restored synthetic source'
                             WHERE evidence_id=%s
                        """, (evidence_id,))

                with runtime.unit_of_work() as tx:
                    submitted = review.submit_in_transaction(
                        tx, actor_id=actor, subject_type="CAP-01",
                        subject_id=baseline.baseline_id,
                        subject_version_id=version.baseline_version_id,
                        reviewer_ids=(reviewer_one, reviewer_two),
                        policy_code="DEPLOYMENT_ALL_V1",
                        trace_id=uuid.uuid4(),
                    )
                    tx.commit()

                try:
                    version_service.create(CreateCapabilityVersion(
                        admin_token, CSRF, uuid.uuid4(), baseline.baseline_id, 2,
                        (item,), str(uuid.uuid4()),
                    ))
                except CapabilityVersionCreateError as error:
                    assert error.code == "CONFLICT_VERSION", error.code
                else:
                    raise AssertionError("replacement Draft entered active Review")

                with runtime.unit_of_work() as tx:
                    first = review.decide_in_transaction(
                        tx, actor_id=reviewer_one,
                        review_id=submitted.review_id,
                        round_id=submitted.round_id,
                        trace_id=uuid.uuid4(),
                        decision=ReviewDecisionKind.APPROVE,
                    )
                    assert first.state.value == "IN_REVIEW"
                    tx.commit()
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.auth_users SET state='DISABLED' "
                        "WHERE user_id=%s", (reviewer_two,),
                    )
                try:
                    with runtime.unit_of_work() as tx:
                        review.decide_in_transaction(
                            tx, actor_id=reviewer_two,
                            review_id=submitted.review_id,
                            round_id=submitted.round_id,
                            trace_id=uuid.uuid4(),
                            decision=ReviewDecisionKind.APPROVE,
                        )
                        tx.commit()
                except ReviewSubjectAccessDenied:
                    pass
                else:
                    raise AssertionError("disabled reviewer decision accepted")
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.auth_users SET state='ENABLED' "
                        "WHERE user_id=%s", (reviewer_two,),
                    )
                if terminal_enabled:
                    with runtime.unit_of_work() as tx:
                        approved = review.decide_in_transaction(
                            tx, actor_id=reviewer_two,
                            review_id=submitted.review_id,
                            round_id=submitted.round_id,
                            trace_id=uuid.uuid4(),
                            decision=ReviewDecisionKind.APPROVE,
                        )
                        assert approved.state.value == "APPROVED"
                        tx.commit()
                    returned_version = version_service.create(
                        CreateCapabilityVersion(
                            admin_token, CSRF, uuid.uuid4(),
                            baseline.baseline_id, 3, (item,),
                            str(uuid.uuid4()),
                        )
                    )
                    with runtime.unit_of_work() as tx:
                        returned_review = review.submit_in_transaction(
                            tx, actor_id=actor, subject_type="CAP-01",
                            subject_id=baseline.baseline_id,
                            subject_version_id=returned_version.baseline_version_id,
                            reviewer_ids=(reviewer_one,),
                            policy_code="DEPLOYMENT_ALL_V1",
                            trace_id=uuid.uuid4(),
                        )
                        tx.commit()
                    with runtime.unit_of_work() as tx:
                        returned = review.decide_in_transaction(
                            tx, actor_id=reviewer_one,
                            review_id=returned_review.review_id,
                            round_id=returned_review.round_id,
                            trace_id=uuid.uuid4(),
                            decision=ReviewDecisionKind.RETURN,
                            comment="synthetic revision required",
                        )
                        assert returned.state.value == "RETURNED"
                        tx.commit()
                    withdrawn_version = version_service.create(
                        CreateCapabilityVersion(
                            admin_token, CSRF, uuid.uuid4(),
                            baseline.baseline_id, 6, (item,),
                            str(uuid.uuid4()),
                        )
                    )
                    with runtime.unit_of_work() as tx:
                        withdrawn_review = review.submit_in_transaction(
                            tx, actor_id=actor, subject_type="CAP-01",
                            subject_id=baseline.baseline_id,
                            subject_version_id=withdrawn_version.baseline_version_id,
                            reviewer_ids=(reviewer_one, reviewer_two),
                            policy_code="DEPLOYMENT_ALL_V1",
                            trace_id=uuid.uuid4(),
                        )
                        tx.commit()
                    with runtime.unit_of_work() as tx:
                        withdrawn = review.withdraw_in_transaction(
                            tx, actor_id=actor,
                            review_id=withdrawn_review.review_id,
                            round_id=withdrawn_review.round_id,
                            trace_id=uuid.uuid4(), expected_version=1,
                            reason="synthetic scope changed",
                        )
                        assert withdrawn.state.value == "WITHDRAWN"
                        tx.commit()
                    final_version = version_service.create(CreateCapabilityVersion(
                        admin_token, CSRF, uuid.uuid4(), baseline.baseline_id, 9,
                        (item,), str(uuid.uuid4()),
                    ))
                    with runtime.unit_of_work() as tx:
                        final_review = review.submit_in_transaction(
                            tx, actor_id=actor, subject_type="CAP-01",
                            subject_id=baseline.baseline_id,
                            subject_version_id=final_version.baseline_version_id,
                            reviewer_ids=(reviewer_two,),
                            policy_code="DEPLOYMENT_ALL_V1",
                            trace_id=uuid.uuid4(),
                        )
                        tx.commit()
                    with runtime.unit_of_work() as tx:
                        review.decide_in_transaction(
                            tx, actor_id=reviewer_two,
                            review_id=final_review.review_id,
                            round_id=final_review.round_id,
                            trace_id=uuid.uuid4(),
                            decision=ReviewDecisionKind.APPROVE,
                        )
                        tx.commit()
                    with connect(name) as db:
                        assert db.execute("""
                            SELECT lock_version,current_approved_version_ref
                              FROM plm.cap_baselines WHERE baseline_id=%s
                        """, (baseline.baseline_id,)).fetchone() == (
                            12, final_version.baseline_version_id,
                        )
                        states = dict(db.execute("""
                            SELECT baseline_version_id,version_state
                              FROM plm.cap_baseline_versions
                             WHERE baseline_id=%s
                        """, (baseline.baseline_id,)).fetchall())
                        assert states == {
                            version.baseline_version_id: "SUPERSEDED",
                            returned_version.baseline_version_id: "RETURNED",
                            withdrawn_version.baseline_version_id: "RETURNED",
                            final_version.baseline_version_id: "APPROVED",
                        }, states
                        assert db.execute("""
                            SELECT count(*) FROM plm.aud_events
                             WHERE target_owner_module='capability'
                               AND action IN ('CAP_VERSION_APPROVED',
                                              'CAP_VERSION_RETURNED',
                                              'CAP_VERSION_WITHDRAWN')
                        """).fetchone()[0] == 4
                    if read_enabled:
                        with connect(name) as db:
                            project_id = db.execute("""
                                INSERT INTO plm.prj_projects(
                                    project_code,project_code_normalized,name,created_by
                                ) VALUES ('CAPREAD','capread','Capability Read',%s)
                                RETURNING project_id
                            """, (actor,)).fetchone()[0]
                            department_id = db.execute("""
                                INSERT INTO plm.prj_departments(
                                    project_id,department_code,
                                    department_code_normalized,name
                                ) VALUES (%s,'READ','read','Read Team')
                                RETURNING department_id
                            """, (project_id,)).fetchone()[0]
                            db.execute("""
                                INSERT INTO plm.prj_project_members(
                                    project_id,user_id,department_id,project_role
                                ) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')
                            """, (project_id, reviewer_one, department_id))
                        reader = CapabilityReadService(
                            unit_of_work=runtime.unit_of_work,
                            session_access=SqlAlchemyProjectReadAccess(),
                            current_user=SqlAlchemyCurrentUserAccess(),
                            membership=SqlAlchemyCapabilityReadMembership(),
                            license_guard=guard,
                            repository=SqlAlchemyCapabilityReadRepository(),
                            clock=lambda: now,
                        )
                        admin_query = CapabilityReadQuery(admin_token, uuid.uuid4())
                        member_query = CapabilityReadQuery(b"b" * 32, uuid.uuid4())
                        outsider_query = CapabilityReadQuery(b"c" * 32, uuid.uuid4())
                        admin_versions = reader.list_versions(
                            admin_query, baseline_id=baseline.baseline_id,
                            page_size=20,
                        )
                        assert [entry.state for entry in admin_versions.items] == [
                            "APPROVED", "RETURNED", "RETURNED", "SUPERSEDED",
                        ]
                        member_baselines = reader.list_baselines(
                            member_query, page_size=20,
                        )
                        assert len(member_baselines.items) == 1
                        member_versions = reader.list_versions(
                            member_query, baseline_id=baseline.baseline_id,
                            page_size=20,
                        )
                        assert [entry.baseline_version_id for entry in member_versions.items] == [
                            final_version.baseline_version_id,
                        ]
                        member_items = reader.list_items(
                            member_query, baseline_id=baseline.baseline_id,
                            baseline_version_id=final_version.baseline_version_id,
                            page_size=20,
                        )
                        assert len(member_items.items) == 1
                        try:
                            reader.get_version(
                                member_query, baseline_id=baseline.baseline_id,
                                baseline_version_id=version.baseline_version_id,
                            )
                        except CapabilityReadError as error:
                            assert error.code == "RESOURCE_NOT_FOUND"
                        else:
                            raise AssertionError("member discovered superseded Version")
                        try:
                            reader.list_baselines(outsider_query, page_size=20)
                        except CapabilityReadError as error:
                            assert error.code == "AUTH_ACCESS_DENIED"
                        else:
                            raise AssertionError("nonmember read GLOBAL Capability")
                        print(
                            "CAP_01_A05_A02_READ_OWNER_PASS: admin history, current "
                            "approved member projection and nonmember denial verified"
                        )
                    try:
                        command.downgrade(cfg, "20261005_0093")
                    except Exception as error:
                        assert "Capability terminal history prevents downgrade" in str(error)
                    else:
                        raise AssertionError("Schema0094 downgraded terminal history")
                    print(
                        "CAP_01_A04_A04_TERMINAL_FORMALIZATION_PASS: approved "
                        "pointer, supersede, returned/withdrawn preservation and "
                        "post-terminal Draft creation verified"
                    )
                else:
                    try:
                        with runtime.unit_of_work() as tx:
                            review.decide_in_transaction(
                                tx, actor_id=reviewer_two,
                                review_id=submitted.review_id,
                                round_id=submitted.round_id,
                                trace_id=uuid.uuid4(),
                                decision=ReviewDecisionKind.APPROVE,
                            )
                            tx.commit()
                    except ReviewSubjectTransitionError:
                        pass
                    else:
                        raise AssertionError("A03 accepted terminal formalization")
                    with connect(name) as db:
                        assert db.execute("""
                            SELECT version_state,review_ref,review_round_ref
                              FROM plm.cap_baseline_versions
                             WHERE baseline_version_id=%s
                        """, (version.baseline_version_id,)).fetchone() == (
                            "IN_REVIEW", submitted.review_id, submitted.round_id,
                        )
                        assert db.execute("""
                            SELECT lock_version,current_approved_version_ref
                              FROM plm.cap_baselines WHERE baseline_id=%s
                        """, (baseline.baseline_id,)).fetchone() == (2, None)
                        assert db.execute("""
                            SELECT review_state,lock_version
                              FROM plm.rvw_reviews WHERE review_id=%s
                        """, (submitted.review_id,)).fetchone() == (
                            "IN_REVIEW", 2,
                        )
                    try:
                        command.downgrade(cfg, "20261005_0092")
                    except Exception as error:
                        assert "Capability Review history prevents downgrade" in str(error)
                    else:
                        raise AssertionError("Schema0093 downgraded active Review history")
                    print(
                        "CAP_01_A04_A03_CAPABILITY_SUBJECT_PASS: real Capability "
                        "source/user lock, persistent IN_REVIEW binding, replacement "
                        "Draft fence and terminal fail-closed verified"
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
