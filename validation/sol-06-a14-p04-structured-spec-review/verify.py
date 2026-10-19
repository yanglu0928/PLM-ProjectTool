"""Win11/PG18 proof for SOL-06 unified Review lifecycle ownership."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.review.application.create_review import (
    CreateReview,
    ReviewCreateService,
)
from plm_assistant.modules.review.application.start_round import (
    ReviewStartService,
    StartReviewRound,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound,
    ReviewTransitionCommandService,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.review.infrastructure.transition_repository import (
    SqlAlchemyReviewTransitionRepository,
)
from plm_assistant.modules.solution.application.structured_spec_review_readiness import (
    StructuredSpecReviewReadinessService,
)
from plm_assistant.modules.solution.application.structured_spec_review_subject import (
    StructuredSpecReviewSubjectOwner,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_review_repository import (
    SqlAlchemyStructuredSpecReviewSubjectRepository,
)
from plm_assistant.modules.trace.application.create_link import CreateTraceLinkRefs
from plm_assistant.modules.trace.application.target_proof import (
    TraceResourceVersionRef,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_trace_for_review",
    ROOT / "validation/sol-06-a14-p03-structured-spec-trace/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def verify_historical_migration(port: int) -> None:
    database = "sol06a14p04_" + uuid.uuid4().hex[:8]
    version_id, series_id, project_id, actor_id = (
        uuid.uuid4() for _ in range(4))
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
        autocommit=True,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database)))
    migration = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database=database))
    try:
        command.upgrade(migration, "20261012_0164")
        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin", dbname=database,
        ) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_structured_specs("
                "structured_solution_spec_id,spec_series_id,project_id,"
                "spec_type,version_no,version_state,content_fingerprint,"
                "created_by) VALUES (%s,%s,%s,'MIGRATION_SPEC',1,'DRAFT',%s,%s)",
                (version_id, series_id, project_id, b"h" * 32, actor_id))
        command.upgrade(migration, "head")
        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin", dbname=database,
        ) as db:
            assert db.execute(
                "SELECT version_state,review_ref,review_round_ref FROM "
                "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
                (version_id,)).fetchone() == ("DRAFT", None, None)
        command.check(migration)
        command.downgrade(migration, "20261012_0164")
        command.upgrade(migration, "head")
        command.check(migration)
    finally:
        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
            autocommit=True,
        ) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))


def on_review(
    *, port, runtime, project, manager, token, csrf, second, repository,
    sources, draft, audit, license_guard, evaluator, validation_repository,
    trace_creator, **_unused,
) -> None:
    verify_historical_migration(port)
    authorization_repository = SqlAlchemyProjectAuthorizationRepository()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=authorization_repository)
    reviewers = ProjectReviewerQualificationService(
        users=SqlAlchemyReviewUserAccess(), projects=authorization_repository)
    subject_repository = SqlAlchemyStructuredSpecReviewSubjectRepository()
    owner = StructuredSpecReviewSubjectOwner(
        repository=subject_repository,
        reviewers=reviewers,
        readiness=StructuredSpecReviewReadinessService(
            repository=validation_repository, evaluator=evaluator),
        audit=audit)
    access = SqlAlchemyProjectWriteAccess()
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=access, projects=authorization,
        license_guard=license_guard, receipts=SqlAlchemyIdempotencyReceipts(),
        audit=audit, subjects=owner,
        clock=lambda: datetime.now(timezone.utc))
    creator = ReviewCreateService(
        **common, repository=SqlAlchemyReviewCreationRepository())
    starter = ReviewStartService(
        **common, reviewers=reviewers,
        repository=SqlAlchemyReviewStartRepository())
    transitions = ReviewTransitionCommandService(
        **common, repository=SqlAlchemyReviewTransitionRepository())

    requirement = draft.requirement_refs[0]
    source_ref = TraceResourceVersionRef(
        "REQ-03", requirement.requirement_id,
        requirement.requirement_version_id)

    with runtime.unit_of_work() as tx:
        actor = access.authenticated_user(
            tx, session_token=token, csrf_token=csrf,
            now=datetime.now(timezone.utc))
        assert actor == manager, (actor, manager)
        permission = authorization.require_in_transaction(
            tx, user_id=actor, project_id=project, operation="REVIEW_CREATE")
        assert permission.project_role == "PROJECT_MANAGER", permission
        creation = owner.authorize_create(
            tx, user_id=actor, project_id=project, subject_type="SOL-06",
            subject_id=second.spec_series_id,
            subject_version_id=second.structured_solution_spec_id)
        assert creation is not None

    def revise(base, suffix):
        revised = replace(
            draft, spec_series_id=base.spec_series_id,
            supersedes_version_ref=base.structured_solution_spec_id)
        with runtime.unit_of_work() as tx:
            proof = sources.prove(
                tx, session_token=token, trace_id=uuid.uuid4(), draft=revised)
            version = repository.create(
                tx, version_id=uuid.uuid4(), actor_id=manager, proof=proof)
            tx.commit()
        trace_creator.create_refs(CreateTraceLinkRefs(
            token, csrf, uuid.uuid4(), project, source_ref,
            TraceResourceVersionRef(
                "SOL-06", version.spec_series_id,
                version.structured_solution_spec_id),
            "IMPLEMENTS"), idempotency_key=f"sol06-review-trace-{suffix}")
        return version

    def review(version, decision, suffix):
        created = creator.create_idempotent(CreateReview(
            token, csrf, uuid.uuid4(), project, "SOL-06",
            version.spec_series_id, version.structured_solution_spec_id),
            idempotency_key=f"sol06-review-create-{suffix}")
        started = starter.start_idempotent(StartReviewRound(
            token, csrf, project, created.review_id,
            version.structured_solution_spec_id, (manager,),
            "STRUCTURED_SPEC_ALL_V1", 0, uuid.uuid4()),
            idempotency_key=f"sol06-review-start-{suffix}")
        result = transitions.decide_idempotent(DecideReviewRound(
            token, csrf, project, created.review_id, started.round_id,
            uuid.uuid4(), decision,
            "Return for correction" if decision is ReviewDecisionKind.RETURN
            else None), idempotency_key=f"sol06-review-decide-{suffix}")
        return created, started, result

    initial_review, initial_round, initial_result = review(
        second, ReviewDecisionKind.APPROVE, "initial")
    assert initial_result.state.value == "APPROVED"

    approved = revise(second, "approved")
    approved_review, approved_round, approved_result = review(
        approved, ReviewDecisionKind.APPROVE, "approved")
    assert approved_result.state.value == "APPROVED"

    returned = revise(approved, "returned")
    returned_review, returned_round, returned_result = review(
        returned, ReviewDecisionKind.RETURN, "returned")
    assert returned_result.state.value == "RETURNED"

    draft_after_return = revise(returned, "tamper")
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        try:
            db.execute(
                "UPDATE plm.sol_structured_specs SET version_state='APPROVED' "
                "WHERE structured_solution_spec_id=%s",
                (draft_after_return.structured_solution_spec_id,))
            db.commit()
        except psycopg.Error:
            db.rollback()
        else:
            raise AssertionError("direct SOL-06 approval must be rejected")

        try:
            db.execute(
                "UPDATE plm.sol_structured_specs SET version_state='IN_REVIEW',"
                "review_ref=%s,review_round_ref=%s "
                "WHERE structured_solution_spec_id=%s",
                (returned_review.review_id, returned_round.round_id,
                 draft_after_return.structured_solution_spec_id))
            db.commit()
        except psycopg.Error:
            db.rollback()
        else:
            raise AssertionError("unreceipted SOL-06 start must be rejected")

        try:
            db.execute(
                "UPDATE plm.sol_spec_review_state_results SET actor_id=%s "
                "WHERE structured_solution_spec_id=%s AND event_type='APPROVED'",
                (uuid.uuid4(), approved.structured_solution_spec_id))
            db.commit()
        except psycopg.Error:
            db.rollback()
        else:
            raise AssertionError("SOL-06 Review receipt must be immutable")

        states = db.execute(
            "SELECT version_state FROM plm.sol_structured_specs "
            "WHERE spec_series_id=%s ORDER BY version_no",
            (second.spec_series_id,)).fetchall()
        assert states == [
            ("DRAFT",), ("SUPERSEDED",), ("APPROVED",),
            ("RETURNED",), ("DRAFT",),
        ], states
        receipts = db.execute(
            "SELECT event_type,structured_solution_spec_id,"
            "previous_approved_version_ref,current_approved_version_ref "
            "FROM plm.sol_spec_review_state_results "
            "WHERE spec_series_id=%s ORDER BY created_at,event_type",
            (second.spec_series_id,)).fetchall()
        assert [row[0] for row in receipts] == [
            "START", "APPROVED", "START", "APPROVED", "START", "RETURNED"
        ], receipts
        assert receipts[1][1] == second.structured_solution_spec_id
        assert receipts[1][2] is None
        assert receipts[1][3] == second.structured_solution_spec_id
        assert receipts[3][1] == approved.structured_solution_spec_id
        assert receipts[3][2] == second.structured_solution_spec_id
        assert receipts[3][3] == approved.structured_solution_spec_id
        assert receipts[5][2] == approved.structured_solution_spec_id
        assert receipts[5][3] == approved.structured_solution_spec_id
        actions = db.execute(
            "SELECT action FROM plm.aud_events WHERE target_object_type='SOL-06' "
            "AND action LIKE 'STRUCTURED_SPEC_VERSION_%' ORDER BY occurred_at"
        ).fetchall()
        assert [row[0] for row in actions] == [
            "STRUCTURED_SPEC_VERSION_APPROVED",
            "STRUCTURED_SPEC_VERSION_APPROVED",
            "STRUCTURED_SPEC_VERSION_RETURNED",
        ], actions

    migration = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.check(migration)
    try:
        command.downgrade(migration, "20261012_0164")
    except RuntimeError as error:
        assert "history prevents downgrade" in str(error)
    else:
        raise AssertionError("Review history must refuse lifecycle downgrade")
    command.check(migration)
    print(
        "SOL_06_A14_P04_REVIEW_PG_PASS: current-fact start/approval, exact "
        "Review binding, supersede, return, immutable receipts, direct-write "
        "closure, downgrade refusal and ORM drift check")
    on_submit = _unused.get("on_submit")
    if on_submit is not None:
        on_submit(
            port=port, runtime=runtime, project=project, manager=manager,
            token=token, csrf=csrf, draft=draft_after_return, audit=audit,
            license_guard=license_guard, access=access,
            authorization=authorization, reviewers=reviewers, owner=owner,
            identity=subject_repository,
            approved_version=approved.structured_solution_spec_id,
            **_unused,
        )


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.on_trace(
        **specs, csrf=created["csrf"], audit=created["audit"],
        license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], on_review=on_review)


if __name__ == "__main__":
    prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created: prior.prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
