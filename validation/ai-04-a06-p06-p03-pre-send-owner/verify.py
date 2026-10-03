"""Windows 11/PostgreSQL 18 proof for post-Begin Provider pre-send facts."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.egress_authorization_owner import (
    EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    require_provider_send,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderPreSendError,
    AIProviderPreSendService,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_execution_route_repository import (
    SqlAlchemyAIProviderExecutionRouteRepository,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import (
    SqlAlchemyAIProviderSecretProof,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(context: dict[str, object], after_authorized=None) -> None:
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p06p03_schema_helper",
    )
    service = AIProviderPreSendService(
        unit_of_work=context["runtime"].unit_of_work,
        claims=AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        ),
        repository=SqlAlchemyAIProviderExecutionRouteRepository(),
        egress_owner=EgressAuthorizationOwner(
            repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
            purposes=context["purposes"],
        ),
        secret_proof=SqlAlchemyAIProviderSecretProof(),
        policies=AIProviderExecutionPolicyRegistry((
            AIProviderExecutionPolicy(
                "endpoint.content-plan.v1",
                ProviderKind.OPENAI_COMPATIBLE,
                "https://api.example.test/v1/chat/completions",
                "cn-beijing",
                "EXTERNAL_APPROVAL_REQUIRED",
                frozenset({"content-plan-chat"}),
                1_000_000, 3, 10, 20,
            ),
        )),
        license_guard=context["guard"],
    )

    def authorize():
        return service.authorize(
            prepared=prepared,
            begun=begun,
            job_id=current.job_id,
            fencing_token=current.fencing_token,
            worker_ref=context["worker_ref"],
            now=datetime.now(timezone.utc),
        )

    try:
        authorize()
    except AIProviderPreSendError:
        pass
    else:
        raise AssertionError("inactive SecretRecord authorized Provider send")

    with schema.connect(context["database"]) as db:
        secret_ref, actor = db.execute(
            "SELECT c.secret_ref,p.created_by FROM plm.ai_provider_config_versions c "
            "JOIN plm.ai_providers p ON p.ai_provider_id=c.ai_provider_id "
            "WHERE c.provider_config_version_id=%s",
            (prepared.grant.provider_config_version_id,),
        ).fetchone()
        secret_version = uuid.uuid4()
        with db.transaction():
            db.execute(
                "INSERT INTO plm.plt_secret_versions(secret_version_id,secret_record_id,"
                "version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by,"
                "activated_at) VALUES (%s,%s,1,%s,'{}'::jsonb,'synthetic-only',%s,"
                "statement_timestamp())",
                (secret_version, secret_ref, b"synthetic-ciphertext", actor),
            )
            db.execute(
                "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',"
                "current_version_ref=%s,lock_version=lock_version+1,"
                "updated_at=statement_timestamp() WHERE secret_record_id=%s",
                (secret_version, secret_ref),
            )

    with schema.connect(context["database"]) as db:
        short_deadline = datetime.now(timezone.utc) + timedelta(seconds=21)
        with db.transaction():
            db.execute(
                "UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
                (short_deadline, current.job_id),
            )
            db.execute(
                "UPDATE plm.job_leases SET lease_expires_at=%s "
                "WHERE job_id=%s AND fencing_token=%s AND state='ACTIVE'",
                (short_deadline, current.job_id, current.fencing_token),
            )
    try:
        authorize()
    except AIProviderPreSendError:
        pass
    else:
        raise AssertionError("insufficient Lease window authorized Provider send")
    with schema.connect(context["database"]) as db:
        renewed_deadline = datetime.now(timezone.utc) + timedelta(seconds=120)
        with db.transaction():
            db.execute(
                "UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
                (renewed_deadline, current.job_id),
            )
            db.execute(
                "UPDATE plm.job_leases SET lease_expires_at=%s "
                "WHERE job_id=%s AND fencing_token=%s AND state='ACTIVE'",
                (renewed_deadline, current.job_id, current.fencing_token),
            )

    result = authorize()
    assert result.route.secret_version_id == secret_version
    assert result.route.ai_provider_id == prepared.grant.ai_provider_id
    assert result.proof.ai_invocation_id == begun.ai_invocation_id
    assert result.proof.fencing_token == current.fencing_token
    require_provider_send(
        result.proof, result.route, prepared.envelope,
        now=datetime.now(timezone.utc),
    )

    with schema.connect(context["database"]) as db:
        db.execute(
            "UPDATE plm.ai_models SET model_state='SUSPENDED',lock_version=lock_version+1 "
            "WHERE ai_model_id=%s", (prepared.grant.ai_model_id,),
        )
    try:
        authorize()
    except AIProviderPreSendError:
        pass
    else:
        raise AssertionError("suspended model authorized Provider send")
    with schema.connect(context["database"]) as db:
        db.execute(
            "UPDATE plm.ai_models SET model_state='AVAILABLE',lock_version=lock_version+1 "
            "WHERE ai_model_id=%s", (prepared.grant.ai_model_id,),
        )
    final_send = authorize()
    assert final_send.proof.ai_invocation_id == begun.ai_invocation_id
    if after_authorized is not None:
        after_authorized({
            **context,
            "authorized_send": final_send,
            "pre_send_service": service,
        })
    print(
        "AI_04_A06_P06_P03_PRE_SEND_OWNER_PASS: Win11/PostgreSQL18.6 "
        "post-Begin PENDING Invocation, current Job fencing, live Authorization, ACTIVE "
        "Provider/current Config, AVAILABLE CHAT Model and exact ACTIVE SecretVersion were "
        "locked and projected into one Lease-bounded Route/SendProof; inactive Secret, "
        "insufficient Lease window and suspended Model failed closed; zero Secret decryption "
        "and zero Provider network I/O\n"
        "AI_04_A06_P06_P05_P02_LEASE_WINDOW_PASS"
    )


def main(after_authorized=None) -> None:
    helper = load_helper(
        "ai-04-a06-p05-p04-claim-envelope-begin", "p06p03_p05_helper",
    )
    helper.main(
        after_begin=lambda context: validate(
            context, after_authorized=after_authorized,
        ),
    )


if __name__ == "__main__":
    main()
