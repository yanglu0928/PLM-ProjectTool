"""Windows 11/PostgreSQL 18 proof for bounded parameterized PROJECT FTS."""

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
    RAGRetrievalQueryPreparationService,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidatePlanner,
)
from plm_assistant.modules.rag.infrastructure.project_fts_candidate_repository import (
    SqlAlchemyProjectFTSCandidateRepository,
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
    "rag_project_fts_claim_fixture",
)
preparation_fixture = load(
    ROOT / "validation/rag-04-a03-p03-retrieval-query-preparation/verify.py",
    "rag_project_fts_preparation_fixture",
)
create_fixture = claim_fixture.create_fixture
begin_fixture = claim_fixture.begin_fixture


def after_claim(context) -> None:
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    claim, claims = context["claim"], context["claims"]
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' WHERE "
            "project_id=%s AND user_id=%s", (project, actor),
        )
        before = db.execute(
            "SELECT (SELECT count(*) FROM plm.rag_retrieval_candidates),"
            "(SELECT count(*) FROM plm.rag_retrieval_score_parts)"
        ).fetchone()
    keys = preparation_fixture.CountingKeys()
    planner = ProjectFTSCandidatePlanner(SqlAlchemyProjectFTSCandidateRepository())
    service = RAGRetrievalQueryPreparationService(
        unit_of_work=runtime.unit_of_work, claims=claims,
        license_guard=create_fixture.activation_fixture.quality_fixture.Guard(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ),
        repository=SqlAlchemyRAGRetrievalQueryPreparationRepository(),
        cipher=AesGcmRetrievalQueryCrypto(keys, key_ref="rag-query-proof.v1"),
        clock=lambda: datetime.now(timezone.utc),
    )
    retained = {}

    def consume(tx, prepared):
        plan = planner.plan(tx, prepared=prepared)
        retained["buffer"] = prepared.query_utf8
        return plan

    plan = service.consume_current_query(
        job_id=claim.job_id, fencing_token=1,
        worker_ref="rag-retrieval-01", consumer=consume,
    )
    assert len(plan.candidates) == 1
    candidate = plan.candidates[0]
    assert candidate.candidate_ordinal == 0
    assert candidate.embedding_index_id == context["planned"].embedding_index_id
    assert candidate.source_type == "PROJECT_RECORD"
    assert candidate.retrieval_channel == "FTS"
    assert candidate.raw_score_micros > 0
    assert candidate.source_locator["locator_type"] == "PARSED_NODE"
    assert bytes(retained["buffer"]) == b"\x00" * 3
    assert keys.calls == 1
    with begin_fixture.connect(database) as db:
        after = db.execute(
            "SELECT (SELECT count(*) FROM plm.rag_retrieval_candidates),"
            "(SELECT count(*) FROM plm.rag_retrieval_score_parts)"
        ).fetchone()
        assert after == before == (0, 0)
    print(
        "RAG_04_A03_P04_PROJECT_FTS_PASS: bound simple websearch query and fixed "
        "metadata predicates returned one stable same-Project/same-Index candidate; "
        "the plan contained no body/vector and Candidate/Score tables remained empty"
    )


def main() -> None:
    claim_fixture.main(after_claim=after_claim, retrieval_query="PLM")


if __name__ == "__main__":
    main()
