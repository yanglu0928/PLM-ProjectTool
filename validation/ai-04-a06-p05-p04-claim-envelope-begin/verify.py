"""Windows 11/PG18 proof for Claim -> Envelope -> Invocation Begin."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContentOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginError,
    AITaskInvocationBeginService,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AITaskInvocationPrepareError,
    AITaskInvocationPrepareService,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_content_repository import (
    SqlAlchemyAIExecutionPromptTaskContentRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_grant_repository import (
    SqlAlchemyAITaskExecutionGrantRepository,
)
from plm_assistant.modules.ai.infrastructure.task_invocation_begin_repository import (
    SqlAlchemyAITaskInvocationBeginRepository,
)
from plm_assistant.modules.document.application.ai_content import DocumentAIContentService
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


def load_composition():
    path = (
        Path(__file__).resolve().parents[1]
        / "ai-04-a06-p04-p04-a06-windows-composition"
        / "verify.py"
    )
    spec = importlib.util.spec_from_file_location("p05p04_composition", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(context: dict[str, object]) -> None:
    runtime = context["runtime"]
    guard = context["guard"]
    worker = "ai-invocation-worker-01"
    schema = load_composition().load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p05p04_schema_priority",
    )
    with schema.connect(context["database"]) as db:
        db.execute(
            "UPDATE plm.job_jobs SET priority=100 WHERE job_id=%s",
            (context["job_id"],),
        )
    leases = JobLeaseService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyJobLeaseRepository(),
    )
    current = leases.claim_next(worker_ref=worker, lease_seconds=120)
    assert current is not None and current.job_id == context["job_id"]
    issuer = AITaskExecutionGrantIssuer(
        unit_of_work=runtime.unit_of_work,
        claims=AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        ),
        repository=SqlAlchemyAITaskExecutionGrantRepository(),
        egress_owner=EgressAuthorizationOwner(
            repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
            purposes=context["purposes"],
        ),
        license_guard=guard,
    )
    projects = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    document_owner = AIDocumentContentOwner(DocumentAIContentService(
        repository=SqlAlchemyDocumentAIContentRepository(),
        storage=LocalParseResultStorage(context["result_root"]),
        projects=projects,
        license_guard=guard,
    ))
    prepare = AITaskInvocationPrepareService(
        unit_of_work=runtime.unit_of_work,
        grants=issuer,
        plans=AIExecutionContentPlanOwner(
            SqlAlchemyAIExecutionContentPlanRepository(),
        ),
        prompts=AIExecutionPromptTaskContentOwner(
            SqlAlchemyAIExecutionPromptTaskContentRepository(),
        ),
        source_owners={"DOC-02": document_owner},
        envelopes=AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"}),
            ),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                Utf8ByteUpperBoundTokenEstimator(),
            )),
        ),
    )
    now = datetime.now(timezone.utc)
    try:
        prepare.prepare(
            job_id=current.job_id, fencing_token=current.fencing_token + 1,
            worker_ref=worker, now=now,
        )
    except AITaskInvocationPrepareError:
        pass
    else:
        raise AssertionError("stale fencing token prepared provider payload")
    prepared = prepare.prepare(
        job_id=current.job_id, fencing_token=current.fencing_token,
        worker_ref=worker, now=now,
    )
    assert prepared.grant.ai_task_id == context["ai_task_id"]
    assert prepared.envelope.payload_fingerprint == (
        prepared.grant.approved_payload_fingerprint
    )
    assert "客户需求 A" in prepared.envelope.canonical_bytes.decode("utf-8")
    begin = AITaskInvocationBeginService(
        unit_of_work=runtime.unit_of_work,
        grants=issuer,
        repository=SqlAlchemyAITaskInvocationBeginRepository(),
    )
    drifted = replace(prepared.payload_plan, payload_fingerprint=b"z" * 32)
    try:
        begin.begin(
            job_id=current.job_id, fencing_token=current.fencing_token,
            worker_ref=worker, now=datetime.now(timezone.utc),
            payload_plan=drifted,
        )
    except AITaskInvocationBeginError:
        pass
    else:
        raise AssertionError("drifted payload proof created Invocation")
    begun = begin.begin(
        job_id=current.job_id, fencing_token=current.fencing_token,
        worker_ref=worker, now=datetime.now(timezone.utc),
        payload_plan=prepared.payload_plan,
    )
    with schema.connect(context["database"]) as db:
        row = db.execute(
            "SELECT i.ai_invocation_id,i.invocation_state,i.content_plan_ref,"
            "i.request_payload_fingerprint,t.current_invocation_ref,t.task_state,"
            "t.lock_version FROM plm.ai_invocations i JOIN plm.ai_tasks t "
            "ON t.ai_task_id=i.ai_task_id WHERE i.ai_task_id=%s",
            (context["ai_task_id"],),
        ).fetchone()
        assert row is not None
        assert row[0] == begun.ai_invocation_id == row[4]
        assert row[1] == "PENDING" and row[2] == prepared.grant.content_plan_id
        assert bytes(row[3]) == prepared.envelope.payload_fingerprint
        assert row[5:] == ("RUNNING", 1)
        assert db.execute(
            "SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s",
            (context["ai_task_id"],),
        ).fetchone()[0] == 1
    print(
        "AI_04_A06_P05_P04_CLAIM_ENVELOPE_BEGIN_PASS: Win11/PostgreSQL18.6 "
        "real Job claim and fencing issued the exact Grant, immutable Plan/Prompt/Document "
        "owners rebuilt the approved Envelope, drifted proof rolled back, and the reissued "
        "Grant atomically began one PENDING Invocation; zero Provider I/O"
    )


def main() -> None:
    load_composition().main(after_validation=validate)


if __name__ == "__main__":
    main()
