"""Windows 11/PostgreSQL 18 proof for authorized Retrieval creation."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.application.create_retrieval import (
    CreateProjectRetrieval,
    RAGRetrievalCreateError,
    RAGRetrievalCreateService,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    RetrievalQueryEnvelope,
)
from plm_assistant.modules.rag.infrastructure.retrieval_create_repository import (
    SqlAlchemyRAGRetrievalCreateRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import (
    AesGcmRetrievalQueryCrypto,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


activation_fixture = load(
    ROOT / "validation/rag-03-a05-p04-p04-index-activation/verify.py",
    "rag_retrieval_create_activation_fixture",
)
begin_fixture = activation_fixture.begin_fixture
CSRF = activation_fixture.CSRF


class Keys:
    def __init__(self) -> None:
        self.key = b"retrieval-create-proof-key-00001"
        assert len(self.key) == 32

    def resolve_key(self, key_ref: str) -> bytes | None:
        return self.key if key_ref == "rag-query-proof.v1" else None


class FailedAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit outage")


def expect(code: str, action) -> None:
    try:
        action()
    except RAGRetrievalCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def execute(context, envelope, sender, adapter, *, query_text=None) -> None:
    activation_fixture.execute(context, envelope, sender, adapter)
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    token = b"z" * 32
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )

    guard = activation_fixture.quality_fixture.Guard()
    keys = Keys()
    cipher = AesGcmRetrievalQueryCrypto(keys, key_ref="rag-query-proof.v1")
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )

    def service(audit=None):
        return RAGRetrievalCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard,
            authorization=authorization,
            cipher=cipher,
            repository=SqlAlchemyRAGRetrievalCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit or AuditService(SqlAlchemyAuditRepository()),
            clock=lambda: datetime.now(timezone.utc),
        )

    query = query_text or "RAG04P02 synthetic unique plaintext marker"
    command = CreateProjectRetrieval(
        token, CSRF, uuid.uuid4(), project, query,
        {"source_type": ["PROJECT_RECORD"]},
        index_id, None, "fts.project.v1", "none.v1", 5,
        str(uuid.uuid4()),
    )

    expect("AUTH_ACCESS_DENIED", lambda: service().create(replace(
        command, csrf_token=b"x" * 32,
    )))
    guard.enabled = False
    expect("LICENSE_OPERATION_DENIED", lambda: service().create(command))
    guard.enabled = True
    expect("RAG_ACTIVE_INDEX_NOT_FOUND", lambda: service().create(replace(
        command, project_index_ref=uuid.uuid4(),
        idempotency_key=str(uuid.uuid4()),
    )))

    with begin_fixture.connect(database) as db:
        before = db.execute(
            "SELECT (SELECT count(*) FROM plm.rag_retrieval_runs),"
            "(SELECT count(*) FROM plm.rag_retrieval_query_contents),"
            "(SELECT count(*) FROM plm.job_jobs WHERE job_type='RAG_RETRIEVAL'),"
            "(SELECT count(*) FROM plm.aud_events WHERE action='RAG_RETRIEVAL_CREATED'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_RAG_RETRIEVAL_CREATE')",
        ).fetchone()
    rollback = replace(
        command, trace_id=uuid.uuid4(), idempotency_key=str(uuid.uuid4()),
    )
    expect("RAG_RETRIEVAL_UNAVAILABLE", lambda: service(
        FailedAudit(),
    ).create(rollback))
    with begin_fixture.connect(database) as db:
        after = db.execute(
            "SELECT (SELECT count(*) FROM plm.rag_retrieval_runs),"
            "(SELECT count(*) FROM plm.rag_retrieval_query_contents),"
            "(SELECT count(*) FROM plm.job_jobs WHERE job_type='RAG_RETRIEVAL'),"
            "(SELECT count(*) FROM plm.aud_events WHERE action='RAG_RETRIEVAL_CREATED'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_RAG_RETRIEVAL_CREATE')",
        ).fetchone()
        assert after == before, (before, after)

    result = service().create(command)
    assert result.project_id == project and result.retrieval_state == "RUNNING"
    assert service().create(command) == result

    with begin_fixture.connect(database) as db:
        run = db.execute(
            "SELECT project_id,actor_ref,project_index_ref,retrieval_policy_ref,"
            "rerank_policy_ref,top_k,retrieval_state,job_id,query_fingerprint "
            "FROM plm.rag_retrieval_runs WHERE retrieval_run_id=%s",
            (result.retrieval_run_id,),
        ).fetchone()
        assert run[:8] == (
            project, actor, index_id, "fts.project.v1", "none.v1", 5,
            "RUNNING", result.job_id,
        )
        content = db.execute(
            "SELECT project_id,query_fingerprint,encrypted_payload,"
            "encryption_metadata,key_provider_ref,plaintext_bytes,retention_until "
            "FROM plm.rag_retrieval_query_contents WHERE retrieval_run_id=%s",
            (result.retrieval_run_id,),
        ).fetchone()
        assert content is not None
        assert content[0] == project and bytes(content[1]) == bytes(run[8])
        assert bytes(content[2]) != query.encode("utf-8")
        assert content[4] == "rag-query-proof.v1"
        assert content[5] == len(query.encode("utf-8"))
        job = db.execute(
            "SELECT payload_refs,state,max_attempts,row_to_json(job_jobs)::text "
            "FROM plm.job_jobs WHERE job_id=%s", (result.job_id,),
        ).fetchone()
        assert job[:3] == (
            {"retrieval_run_id": str(result.retrieval_run_id)}, "PENDING", 1,
        )
        assert query not in job[3]
        audit = db.execute(
            "SELECT count(*),min(row_to_json(aud_events)::text) FROM plm.aud_events "
            "WHERE action='RAG_RETRIEVAL_CREATED' AND target_object_id=%s",
            (result.retrieval_run_id,),
        ).fetchone()
        assert audit[0] == 1 and query not in audit[1]
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_RAG_RETRIEVAL_CREATE' AND state='COMPLETED' AND "
            "result_ref_id=%s AND result_status=202",
            (result.retrieval_run_id,),
        ).fetchone()[0] == 1

        decrypted = cipher.decrypt(RetrievalQueryEnvelope(
            result.retrieval_run_id, project, bytes(content[1]), bytes(content[2]),
            content[3], content[4], content[5], content[6],
        ))
        assert bytes(decrypted) == query.encode("utf-8")
        decrypted[:] = b"\x00" * len(decrypted)

        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )
    expect("RESOURCE_NOT_FOUND", lambda: service().create(command))
    print(
        "RAG_04_A02_P02_RETRIEVAL_CREATE_PASS: current Session/CSRF, License, "
        "membership and ACTIVE Index were rechecked; Job, Run, encrypted query, "
        "Audit and receipt committed atomically; rollback/replay/revocation were "
        "verified and no Provider I/O or customer data egress occurred"
    )


def main(*, query_text=None) -> None:
    def validate(context, envelope, sender, adapter):
        execute(
            context, envelope, sender, adapter, query_text=query_text,
        )

    activation_fixture.send_fixture.main(
        execute=validate, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
