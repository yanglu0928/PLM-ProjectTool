"""Windows 11/PostgreSQL 18 proof for atomic RAG index activation."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.rag.application.embedding_index_activation import (
    ActivateRAGEmbeddingIndex,
    RAGEmbeddingIndexActivationError,
    RAGEmbeddingIndexActivationService,
)
from plm_assistant.modules.rag.application.embedding_index_quality import (
    RAGEmbeddingIndexQualityService,
    RegisterRAGEmbeddingIndexQuality,
)
from plm_assistant.modules.rag.infrastructure.embedding_index_activation_repository import (
    SqlAlchemyRAGEmbeddingIndexActivationRepository,
)
from plm_assistant.modules.rag.infrastructure.embedding_index_quality_repository import (
    SqlAlchemyRAGEmbeddingIndexQualityRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quality_fixture = load(
    ROOT / "validation/rag-03-a05-p04-p03-quality-owner/verify.py",
    "rag_activation_quality_fixture",
)
ready_fixture = quality_fixture.ready_fixture
send_fixture = quality_fixture.send_fixture
begin_fixture = quality_fixture.begin_fixture
CSRF = quality_fixture.CSRF


class FailedAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit outage")


def expect(code: str, action) -> None:
    try:
        action()
    except RAGEmbeddingIndexActivationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def execute(context, envelope, sender, adapter) -> None:
    ready_fixture.execute_success(context, envelope, sender, adapter)
    database, runtime = context["database"], context["runtime"]
    index_id, actor = context["planned"].embedding_index_id, context["actor"]
    token = b"z" * 32
    quality_fixture._enable_project_manager(
        database, actor, context["project"], token,
    )
    guard = quality_fixture.Guard()
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(),
        license_guard=guard,
        receipts=SqlAlchemyIdempotencyReceipts(),
        clock=lambda: datetime.now(timezone.utc),
    )
    quality = RAGEmbeddingIndexQualityService(
        **common,
        repository=SqlAlchemyRAGEmbeddingIndexQualityRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()),
    ).register(RegisterRAGEmbeddingIndexQuality(
        token, CSRF, uuid.uuid4(), index_id, 2,
        "quality.synthetic.activation.v1", b"a" * 32,
        hashlib.sha256(b"synthetic isolation activation").digest(),
        hashlib.sha256(b"synthetic activation evaluation").digest(),
        50, 45, 49, True, 0, True,
        datetime.now(timezone.utc) - timedelta(days=1), str(uuid.uuid4()),
    ))
    assert quality.quality_state == "PASSED"

    def service(audit=None):
        return RAGEmbeddingIndexActivationService(
            **common,
            repository=SqlAlchemyRAGEmbeddingIndexActivationRepository(),
            audit=audit or AuditService(SqlAlchemyAuditRepository()),
        )

    command = ActivateRAGEmbeddingIndex(
        token, CSRF, uuid.uuid4(), index_id, 2, str(uuid.uuid4()),
    )
    expect("AUTH_ACCESS_DENIED", lambda: service().activate(replace(
        command, csrf_token=b"x" * 32,
    )))
    guard.enabled = False
    expect("LICENSE_OPERATION_DENIED", lambda: service().activate(command))
    guard.enabled = True
    expect("RAG_INDEX_ACTIVATION_UNAVAILABLE", lambda: service(
        FailedAudit(),
    ).activate(command))
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT index_state,lock_version FROM plm.rag_embedding_indexes "
            "WHERE embedding_index_id=%s", (index_id,),
        ).fetchone() == ("READY", 2)
        assert db.execute(
            "SELECT count(*) FROM plm.rag_embedding_index_activation_results",
        ).fetchone()[0] == 0

    result = service().activate(command)
    assert result.quality_result_ref == quality.quality_result_id
    assert (result.lock_version, result.retired_index_ref) == (3, None)
    assert service().activate(command) == result
    expect("CONFLICT_VERSION", lambda: service().activate(replace(
        command, idempotency_key=str(uuid.uuid4()),
    )))
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT index_state,lock_version FROM plm.rag_embedding_indexes "
            "WHERE embedding_index_id=%s", (index_id,),
        ).fetchone() == ("ACTIVE", 3)
        assert db.execute(
            "SELECT count(*) FROM plm.rag_embedding_index_activation_results "
            "WHERE embedding_index_id=%s AND quality_result_ref=%s",
            (index_id, quality.quality_result_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='RAG_INDEX_ACTIVATED' AND target_object_id=%s AND "
            "target_version_id=%s", (index_id, quality.quality_result_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_RAG_INDEX_ACTIVATE' AND state='COMPLETED'",
        ).fetchone()[0] == 1
        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
            "project_id=%s AND user_id=%s", (context["project"], actor),
        )
    expect("AUTH_ACCESS_DENIED", lambda: service().activate(command))
    print(
        "RAG_03_A05_P04_P04_INDEX_ACTIVATION_PASS: current quality/model/source/"
        "authorization facts, Session/CSRF, ProjectManager and License were "
        "rechecked; Audit, ACTIVE/v3, ActivationResult and receipt committed "
        "atomically; replay re-authorized and no real Provider I/O occurred"
    )


def main() -> None:
    send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
