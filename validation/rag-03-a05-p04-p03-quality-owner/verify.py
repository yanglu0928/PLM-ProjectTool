"""Windows 11/PostgreSQL 18 proof for authorized RAG quality registration."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.rag.application.embedding_index_quality import (
    RAGEmbeddingIndexQualityError,
    RAGEmbeddingIndexQualityService,
    RegisterRAGEmbeddingIndexQuality,
)
from plm_assistant.modules.rag.infrastructure.embedding_index_quality_repository import (
    SqlAlchemyRAGEmbeddingIndexQualityRepository,
)


ROOT = Path(__file__).resolve().parents[2]
CSRF = b"c" * 32


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ready_fixture = load(
    ROOT / "validation/rag-03-a05-p03-index-ready-owner/verify.py",
    "rag_quality_owner_ready_fixture",
)
send_fixture = ready_fixture.send_fixture
begin_fixture = ready_fixture.begin_fixture


class Guard:
    enabled = True

    def require_valid(self, **_kwargs):
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class FailedAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit outage")


def expect(code: str, action) -> None:
    try:
        action()
    except RAGEmbeddingIndexQualityError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def _enable_project_manager(database: str, actor: uuid.UUID, project: uuid.UUID,
                            token: bytes) -> None:
    with begin_fixture.connect(database) as db:
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
            "password_hash,algorithm_id,parameter_set) VALUES "
            "(%s,1,'$synthetic$quality-owner','TEST_ONLY','{}'::jsonb) "
            "RETURNING password_credential_id", (actor,),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
            (credential, actor),
        )
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES "
            "(%s,'RAGQA','ragqa','Synthetic RAG Quality') RETURNING department_id",
            (project,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
            "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
            (project, actor, department),
        )
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) VALUES "
            "(%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
            "statement_timestamp()+interval '1 hour')",
            (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), actor),
        )


def execute(context, envelope, sender, adapter) -> None:
    ready_fixture.execute_success(context, envelope, sender, adapter)
    database = context["database"]
    index_id = context["planned"].embedding_index_id
    actor = context["actor"]
    token = b"q" * 32
    _enable_project_manager(database, actor, context["project"], token)
    guard = Guard()

    def service(audit=None):
        return RAGEmbeddingIndexQualityService(
            unit_of_work=context["runtime"].unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard,
            repository=SqlAlchemyRAGEmbeddingIndexQualityRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit or AuditService(SqlAlchemyAuditRepository()),
            clock=lambda: datetime.now(timezone.utc),
        )

    base = RegisterRAGEmbeddingIndexQuality(
        token, CSRF, uuid.uuid4(), index_id, 2,
        "quality.synthetic.failed.owner.v1", b"f" * 32,
        hashlib.sha256(b"synthetic isolation failed evidence").digest(),
        hashlib.sha256(b"synthetic failed evaluation artifact").digest(),
        50, 24, 37, True, 0, True,
        datetime.now(timezone.utc) - timedelta(days=1), str(uuid.uuid4()),
    )
    expect("AUTH_ACCESS_DENIED", lambda: service().register(replace(
        base, csrf_token=b"x" * 32,
    )))
    guard.enabled = False
    expect("LICENSE_OPERATION_DENIED", lambda: service().register(base))
    guard.enabled = True

    failed = service().register(base)
    assert failed.quality_state == "FAILED"
    assert failed.classification_basis_points == 4800
    assert failed.exact_citation_basis_points == 7400
    assert service().register(base) == failed
    expect("CONFLICT_IDEMPOTENCY", lambda: service().register(replace(
        base, classification_correct_count=25,
    )))

    rollback = replace(
        base, trace_id=uuid.uuid4(),
        dataset_ref="quality.synthetic.rollback.owner.v1",
        dataset_fingerprint=b"r" * 32,
        classification_correct_count=45,
        exact_citation_correct_count=49,
        idempotency_key=str(uuid.uuid4()),
    )
    expect("RAG_INDEX_QUALITY_UNAVAILABLE", lambda: service(
        FailedAudit(),
    ).register(rollback))
    passed = service().register(rollback)
    assert passed.quality_state == "PASSED"
    assert (passed.classification_basis_points,
            passed.exact_citation_basis_points) == (9000, 9800)

    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT index_state,lock_version FROM plm.rag_embedding_indexes "
            "WHERE embedding_index_id=%s", (index_id,),
        ).fetchone() == ("READY", 2)
        assert db.execute(
            "SELECT array_agg(quality_state ORDER BY completed_at),count(*) "
            "FROM plm.rag_embedding_index_quality_results WHERE "
            "embedding_index_id=%s", (index_id,),
        ).fetchone() == (["FAILED", "PASSED"], 2)
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='RAG_INDEX_QUALITY_RECORDED' AND target_object_id=%s",
            (index_id,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_RAG_INDEX_QUALITY_REGISTER' AND state='COMPLETED'",
        ).fetchone()[0] == 2
        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
            "project_id=%s AND user_id=%s", (context["project"], actor),
        )
    expect("AUTH_ACCESS_DENIED", lambda: service().register(base))
    print(
        "RAG_03_A05_P04_P03_QUALITY_OWNER_PASS: Session/CSRF, current "
        "ProjectManager, License recheck, server-derived 90/98 result, failed "
        "evidence retention, idempotent replay/conflict and audit rollback verified; "
        "Index remains READY and no query/answer body is accepted"
    )


def main() -> None:
    send_fixture.main(
        execute=execute,
        source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
