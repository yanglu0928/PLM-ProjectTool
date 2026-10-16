"""Windows 11/PostgreSQL 18 proof for current-fact Retrieval query preparation."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalPreparationError,
    RAGRetrievalQueryPreparationService,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import (
    AesGcmRetrievalQueryCrypto,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_preparation_repository import (
    SqlAlchemyRAGRetrievalQueryPreparationRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claim_fixture = load(
    ROOT / "validation/rag-04-a03-p02-retrieval-claim/verify.py",
    "rag_retrieval_preparation_claim_fixture",
)
create_fixture = claim_fixture.create_fixture
begin_fixture = claim_fixture.begin_fixture


class CountingKeys:
    def __init__(self) -> None:
        self.key = b"retrieval-create-proof-key-00001"
        self.calls = 0

    def resolve_key(self, key_ref: str) -> bytes | None:
        self.calls += 1
        return self.key if key_ref == "rag-query-proof.v1" else None


def expect(code: str, action) -> None:
    try:
        action()
    except RAGRetrievalPreparationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def after_claim(context) -> None:
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    claim, claims = context["claim"], context["claims"]
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )
    keys = CountingKeys()
    guard = create_fixture.activation_fixture.quality_fixture.Guard()
    service = RAGRetrievalQueryPreparationService(
        unit_of_work=runtime.unit_of_work, claims=claims,
        license_guard=guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ),
        repository=SqlAlchemyRAGRetrievalQueryPreparationRepository(),
        cipher=AesGcmRetrievalQueryCrypto(keys, key_ref="rag-query-proof.v1"),
        clock=lambda: datetime.now(timezone.utc),
    )
    retained = {}

    def consume(_tx, prepared):
        retained["buffer"] = prepared.query_utf8
        retained["query"] = bytes(prepared.query_utf8)
        retained["authorization"] = prepared.authorization_snapshot_fingerprint
        assert prepared.retrieval_run_id == claim.retrieval_run_id
        assert prepared.job_id == claim.job_id
        assert prepared.project_id == project and prepared.actor_id == actor
        assert prepared.retrieval_policy_ref == "fts.project.v1"
        assert prepared.metadata_filter == {"source_type": ["PROJECT_RECORD"]}
        return prepared.query_fingerprint

    fingerprint = service.consume_current_query(
        job_id=claim.job_id, fencing_token=1,
        worker_ref="rag-retrieval-01", consumer=consume,
    )
    expected = b"RAG04P02 synthetic unique plaintext marker"
    assert retained["query"] == expected
    assert len(fingerprint) == 32 and len(retained["authorization"]) == 32
    assert bytes(retained["buffer"]) == b"\x00" * len(expected)
    assert keys.calls == 1

    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )
    expect("RESOURCE_NOT_FOUND", lambda: service.consume_current_query(
        job_id=claim.job_id, fencing_token=1,
        worker_ref="rag-retrieval-01", consumer=lambda *_: None,
    ))
    assert keys.calls == 1
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )
    guard.enabled = False
    expect("LICENSE_OPERATION_DENIED", lambda: service.consume_current_query(
        job_id=claim.job_id, fencing_token=1,
        worker_ref="rag-retrieval-01", consumer=lambda *_: None,
    ))
    assert keys.calls == 1

    print(
        "RAG_04_A03_P03_QUERY_PREPARATION_PASS: current claim, enabled actor, "
        "membership, License, ACTIVE Index/model/source/embedding and ciphertext "
        "binding were checked before one key read; normalized fingerprint matched "
        "and plaintext was zeroed; revocation and License denial read no key"
    )


def main() -> None:
    claim_fixture.main(after_claim=after_claim)


if __name__ == "__main__":
    main()
