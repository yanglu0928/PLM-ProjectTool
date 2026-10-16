"""Windows 11/PostgreSQL 18 proof for AI-owned cancellation semantics."""

from __future__ import annotations

import importlib.util
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.application.cancel_task_execution import (
    AITaskCancellationError,
    AITaskCancellationOwner,
    CancelAITaskExecution,
)
from plm_assistant.modules.ai.application.request_task_cancel import (
    AITaskJobCancelOwner,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
)
from plm_assistant.modules.ai.infrastructure.task_cancellation_repository import (
    SqlAlchemyAITaskCancellationRepository,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.api.cancel import create_project_job_cancel_router
from plm_assistant.modules.jobs.application.cancel_request import (
    ProjectJobCancellation,
)
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.read_repository import (
    SqlAlchemyJobReadRepository,
)
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.secret_store_reader import (
    SqlAlchemyEncryptedSecretStore,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


def command_for(context: dict[str, object], schema, *, reason: str):
    prepared = context["prepared_invocation"]
    with schema.connect(context["database"]) as db:
        version = db.execute(
            "SELECT lock_version FROM plm.ai_tasks WHERE ai_task_id=%s",
            (prepared.grant.ai_task_id,),
        ).fetchone()[0]
    return CancelAITaskExecution(
        prepared.grant.ai_task_id, prepared.grant.project_id,
        prepared.grant.requested_by, uuid.uuid4(), version, reason,
    )


def owner(context: dict[str, object], audit) -> AITaskCancellationOwner:
    return AITaskCancellationOwner(
        unit_of_work=context["runtime"].unit_of_work,
        store=SqlAlchemyAITaskCancellationRepository(), audit=audit,
    )


def cancellation_client(context: dict[str, object]) -> TestClient:
    task_owner = AITaskJobCancelOwner(
        unit_of_work=context["runtime"].unit_of_work,
        store=SqlAlchemyAITaskCancellationRepository(),
        session_access=SqlAlchemyProjectWriteAccess(),
        projects=ProjectAuthorizationService(
            unit_of_work=context["runtime"].unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ),
        license_guard=context["guard"],
        receipts=SqlAlchemyIdempotencyReceipts(), audit=context["audit"],
    )
    router = create_project_job_cancel_router(
        sessions=context["sessions"],
        origins=LoginOriginPolicy([context["origin"]]),
        cancellations=ProjectJobCancellation(
            unit_of_work=context["runtime"].unit_of_work,
            repository=SqlAlchemyJobReadRepository(),
            sessions=context["sessions"], license_guard=context["guard"],
            owners={("ai", "AI_TASK_EXECUTE"): task_owner},
        ),
    )
    return TestClient(
        create_app(job_cancel_router=router), base_url=context["origin"],
    )


def cancellation_headers(
    context: dict[str, object], *, version: int, key: str,
) -> dict[str, str]:
    return {
        "origin": context["origin"],
        "cookie": "plm_session=" + context["session_token"].hex(),
        "x-csrf-token": context["csrf_token"].hex(),
        "idempotency-key": key,
        "if-match": f'"v{version}"',
    }


def http_cancel(
    context: dict[str, object], schema, *, reason: str,
) -> tuple[dict[str, object], str, int]:
    prepared = context["prepared_invocation"]
    current = context["current_claim"]
    with schema.connect(context["database"]) as db:
        version = db.execute(
            "SELECT lock_version FROM plm.job_jobs WHERE job_id=%s",
            (current.job_id,),
        ).fetchone()[0]
    key = str(uuid.uuid4())
    path = (
        f"/api/v1/projects/{prepared.grant.project_id}/jobs/"
        f"{current.job_id}:cancel"
    )
    headers = cancellation_headers(context, version=version, key=key)
    with cancellation_client(context) as client:
        conflict = client.post(
            path, headers={**headers, "if-match": f'"v{version + 1}"'},
            json={"reason": reason},
        )
        assert conflict.status_code == 409, conflict.text
        context["guard"].enabled = False
        try:
            denied = client.post(path, headers=headers, json={"reason": reason})
            assert denied.status_code == 403, denied.text
        finally:
            context["guard"].enabled = True
        response = client.post(path, headers=headers, json={"reason": reason})
        assert response.status_code == 200, response.text
        first = response.json()["data"]
        replay = client.post(path, headers=headers, json={"reason": reason})
        assert replay.status_code == 200 and replay.json()["data"] == first
        changed = client.post(
            path, headers=headers, json={"reason": reason + "（不同）"},
        )
        assert changed.status_code == 409, changed.text
    return first, key, version


def seed_member_session(context: dict[str, object], schema):
    token, csrf = uuid.uuid4().bytes + uuid.uuid4().bytes, uuid.uuid4().bytes + uuid.uuid4().bytes
    username = "synthetic-ai-cancel-member-" + uuid.uuid4().hex[:10]
    with schema.connect(context["database"]) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
            "password_hash,algorithm_id,parameter_set) VALUES "
            "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
            "RETURNING password_credential_id", (actor,),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
            (credential, actor),
        )
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) VALUES "
            "(%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours')",
            (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
        )
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments WHERE project_id=%s "
            "ORDER BY created_at LIMIT 1", (context["project_id"],),
        ).fetchone()[0]
        member = db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
            "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') "
            "RETURNING project_member_id",
            (context["project_id"], actor, department),
        ).fetchone()[0]
    return actor, member, token, csrf


def validate_pre_send(context: dict[str, object]) -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p08p04_pre_schema",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    reason = "用户取消尚未发送的 AI 建议"
    manager, member, manager_token, manager_csrf = seed_member_session(
        context, schema,
    )
    with schema.connect(context["database"]) as db:
        job_version = db.execute(
            "SELECT lock_version FROM plm.job_jobs WHERE job_id=%s",
            (current.job_id,),
        ).fetchone()[0]
    manager_context = {
        **context, "session_token": manager_token, "csrf_token": manager_csrf,
    }
    path = (
        f"/api/v1/projects/{prepared.grant.project_id}/jobs/"
        f"{current.job_id}:cancel"
    )
    with cancellation_client(manager_context) as client:
        denied = client.post(
            path,
            headers=cancellation_headers(
                manager_context, version=job_version, key=str(uuid.uuid4()),
            ),
            json={"reason": reason},
        )
        assert denied.status_code == 404, denied.text
    with schema.connect(context["database"]) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' "
            "WHERE project_member_id=%s", (member,),
        )
    first, _, prior_job_version = http_cancel(
        manager_context, schema, reason=reason,
    )
    assert first["state"] == "CANCELLED" and first["changed"] is True
    assert first["etag"] == f'"v{prior_job_version + 1}"'
    try:
        context["pre_send_service"].authorize(
            prepared=prepared, begun=begun, job_id=current.job_id,
            fencing_token=current.fencing_token,
            worker_ref=context["worker_ref"],
            now=datetime.now(timezone.utc),
        )
    except Exception:
        pass
    else:
        raise AssertionError("cancelled pre-send Task remained send-authorized")
    with schema.connect(context["database"]) as db:
        facts = db.execute(
            "SELECT j.state,j.cancel_requested_by,j.cancel_reason,l.state,"
            "a.error_code,i.invocation_state,t.task_state,t.error_code "
            "FROM plm.job_jobs j JOIN plm.job_leases l ON l.job_id=j.job_id "
            "AND l.fencing_token=j.fencing_token JOIN plm.job_attempts a "
            "ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref WHERE j.job_id=%s",
            (current.job_id,),
        ).fetchone()
        event = db.execute(
            "SELECT actor_id,outcome,reason_code,before_state,after_state "
            "FROM plm.aud_events WHERE action='AI_TASK_CANCELLED' "
            "AND target_object_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
    assert facts == (
        "CANCELLED", manager, reason, "RELEASED",
        "JOB_CANCELLED", "CANCELLED", "CANCELLED", None,
    )
    assert event == (
        manager, "SUCCESS", "USER_REQUESTED",
        "RUNNING", "CANCELLED",
    )
    print(
        "AI_04_A06_P08_P04_PRE_SEND_CANCEL_PASS: Win11/PostgreSQL18.6 "
        "atomically cancelled Job/Attempt/Lease/PENDING Invocation/Task with user "
        "reason and Audit, then rejected Provider send; zero Provider network I/O"
    )


def validate_post_fence(context: dict[str, object]) -> None:
    send_helper = load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p08p04_send_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p08p04_post_schema",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    username = "synthetic-ai-cancel-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
    actor = send_helper.FixedSystemActor(system_id)
    secret_audit = AITaskProviderSecretAccessAudit(
        unit_of_work=context["runtime"].unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()), system_actor=actor,
    )
    decryptor = send_helper.SyntheticDecryptor(
        context["authorized_send"].route.secret_version_id,
    )
    adapter = send_helper.SyntheticAdapter(
        b"synthetic-task-key-not-for-network",
    )
    response = AITaskProviderSendService(
        pre_send=send_helper.CountingPreSend(context["pre_send_service"]),
        secrets=SecretResolver(
            SqlAlchemyEncryptedSecretStore(context["runtime"].unit_of_work),
            decryptor, secret_audit,
        ),
        adapter=adapter, access_audit_scope=secret_audit,
        send_fence=AITaskProviderSendFenceService(
            unit_of_work=context["runtime"].unit_of_work,
            claims=AITaskExecutionClaims(
                repository=SqlAlchemyAITaskExecutionClaimRepository(),
            ),
            repository=SqlAlchemyAITaskProviderSendFenceRepository(),
        ),
        clock=lambda: datetime.now(timezone.utc),
    ).send_once(
        prepared=prepared, begun=begun, job_id=current.job_id,
        fencing_token=current.fencing_token,
        worker_ref=context["worker_ref"],
    )
    response.close()
    assert len(adapter.calls) == 1
    rollback_command = command_for(
        context, schema, reason="用户在发送栅栏后请求取消",
    )
    try:
        owner(context, FailingAudit()).cancel(rollback_command)
    except AITaskCancellationError:
        pass
    else:
        raise AssertionError("Audit failure committed post-fence cancellation")
    with schema.connect(context["database"]) as db:
        rolled_back = db.execute(
            "SELECT j.state,l.state,a.completed_at,i.invocation_state,t.task_state "
            "FROM plm.job_jobs j JOIN plm.job_leases l ON l.job_id=j.job_id "
            "AND l.fencing_token=j.fencing_token JOIN plm.job_attempts a "
            "ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref WHERE j.job_id=%s",
            (current.job_id,),
        ).fetchone()
    assert rolled_back == ("RUNNING", "ACTIVE", None, "RUNNING", "RUNNING")
    first, _, prior_job_version = http_cancel(
        context, schema, reason=rollback_command.reason,
    )
    assert first["state"] == "FAILED" and first["changed"] is False
    assert first["etag"] == f'"v{prior_job_version + 1}"'
    with schema.connect(context["database"]) as db:
        facts = db.execute(
            "SELECT j.state,j.cancel_requested_by,j.cancel_reason,l.state,"
            "a.error_code,i.invocation_state,i.error_code,i.retryable,"
            "t.task_state,t.error_code,t.retryable FROM plm.job_jobs j "
            "JOIN plm.job_leases l ON l.job_id=j.job_id "
            "AND l.fencing_token=j.fencing_token JOIN plm.job_attempts a "
            "ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref WHERE j.job_id=%s",
            (current.job_id,),
        ).fetchone()
        event = db.execute(
            "SELECT actor_id,outcome,reason_code,before_state,after_state "
            "FROM plm.aud_events WHERE action='AI_TASK_CANCEL_OUTCOME_UNKNOWN' "
            "AND target_object_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
    assert facts == (
        "FAILED", None, None, "RELEASED", "AI_PROVIDER_OUTCOME_UNKNOWN",
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
    )
    assert event == (
        prepared.grant.requested_by, "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN",
        "RUNNING", "FAILED",
    )
    assert len(adapter.calls) == 1
    assert all(not any(value) for value in decryptor.buffers)
    print(
        "AI_04_A06_P08_P04_POST_FENCE_CANCEL_PASS: Win11/PostgreSQL18.6 "
        "rolled back on Audit failure, then atomically released execution and "
        "terminalized post-send Job/Attempt/RUNNING Invocation/Task as non-retryable "
        "AI_PROVIDER_OUTCOME_UNKNOWN; one synthetic Adapter call, zero real network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p08p04_pre_send_helper",
    )
    helper.main(after_authorized=validate_pre_send)
    helper.main(after_authorized=validate_post_fence)


if __name__ == "__main__":
    main()
